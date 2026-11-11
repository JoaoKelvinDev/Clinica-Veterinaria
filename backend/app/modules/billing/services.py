from datetime import date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.core.repositories import ClinicContext
from app.modules.billing.models import FinancialEntry
from app.modules.billing.repositories import FinancialRepository
from app.modules.billing.schemas import (
    EntryCreate,
    EntryFilters,
    EntryPage,
    EntryRead,
    FinancialSummary,
    ReversalRead,
)
from app.modules.clinics.models import Role, User
from app.modules.patients.services import PatientService
from app.modules.tutors.services import TutorService


def require_financial_access(actor: User, *, admin: bool = False) -> None:
    allowed = {Role.ADMIN} if admin else {Role.ADMIN, Role.RECEPTION}
    if not actor.active or actor.deleted_at is not None or actor.role not in allowed:
        raise AccessDenied("Seu perfil não permite esta operação financeira.")


class FinancialService:
    def summary(self, actor: User, start: date, end: date) -> FinancialSummary:
        require_financial_access(actor)
        if start > end:
            raise InvalidData("O início do período deve ser anterior ou igual ao fim.")
        income, expense = self.repository.totals(
            EntryFilters(
                start=start, end=end, kind="income" if actor.role == Role.RECEPTION else None
            )
        )
        return FinancialSummary(
            income_cents=str(income),
            expense_cents=str(expense) if actor.role == Role.ADMIN else None,
            difference_cents=str(income - expense) if actor.role == Role.ADMIN else None,
        )

    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "FinancialService":
        return cls(
            FinancialRepository(session, context),
            TutorService.for_clinic(session, context),
            PatientService.for_clinic(session, context),
        )

    def __init__(
        self, repository: FinancialRepository, tutors: TutorService, patients: PatientService
    ) -> None:
        self.repository, self.tutors, self.patients = repository, tutors, patients

    def _read(self, entry: FinancialEntry, reversal: FinancialEntry | None = None) -> EntryRead:
        return EntryRead.model_validate(entry).model_copy(
            update={
                "status": "reversed" if reversal else "posted",
                "reversal": ReversalRead.model_validate(reversal) if reversal else None,
            }
        )

    def _get(self, entry_id: UUID, *, lock: bool = False) -> FinancialEntry:
        entry = self.repository.locked(entry_id) if lock else self.repository.get(entry_id)
        if entry is None or entry.reverses_id is not None:
            raise ResourceNotFound("Lançamento não encontrado.")
        return entry

    def get(self, actor: User, entry_id: UUID) -> EntryRead:
        require_financial_access(actor)
        entry = self._get(entry_id)
        if actor.role == Role.RECEPTION and entry.kind != "income":
            raise ResourceNotFound("Lançamento não encontrado.")
        return self._read(entry, self.repository.reversals([entry_id]).get(entry_id))

    def list(self, actor: User, filters: EntryFilters, limit: int, offset: int) -> EntryPage:
        require_financial_access(actor)
        if filters.start > filters.end:
            raise InvalidData("O início do período deve ser anterior ou igual ao fim.")
        if actor.role == Role.RECEPTION:
            if filters.kind == "expense":
                raise AccessDenied("A recepção pode consultar somente recebimentos.")
            filters = filters.model_copy(update={"kind": "income"})
        rows, total, income, expense = self.repository.list(filters, limit, offset)
        reversals = self.repository.reversals([entry.id for entry in rows])
        return EntryPage(
            items=[self._read(row, reversals.get(row.id)) for row in rows],
            total=total,
            summary=FinancialSummary(
                income_cents=str(income),
                expense_cents=str(expense) if actor.role == Role.ADMIN else None,
                difference_cents=str(income - expense) if actor.role == Role.ADMIN else None,
            ),
        )

    def create(self, actor: User, values: EntryCreate) -> EntryRead:
        require_financial_access(actor, admin=values.kind == "expense")
        if values.occurred_on > datetime.now(ZoneInfo("America/Fortaleza")).date():
            raise InvalidData("Informe a data em que o valor já foi recebido ou pago.")
        tutor = self.tutors.get(values.tutor_id) if values.tutor_id else None
        patient = self.patients.get(values.patient_id) if values.patient_id else None
        if tutor and patient:
            if not any(link.tutor.id == tutor.id for link in self.patients.list_tutors(patient.id)):
                raise InvalidData("O tutor informado não está vinculado ao paciente.")
        entry = FinancialEntry(
            id=uuid4(),
            clinic_id=self.repository.context.clinic_id,
            **values.model_dump(),
            author_id=actor.id,
            author_name=actor.name,
            tutor_name=tutor.name if tutor else None,
            patient_name=patient.name if patient else None,
        )
        self.repository.save(entry)
        return self._read(entry)

    def reverse(self, actor: User, entry_id: UUID, reason: str) -> EntryRead:
        require_financial_access(actor, admin=True)
        reason = reason.strip()
        if not 3 <= len(reason) <= 500:
            raise InvalidData("Descreva o motivo do estorno entre 3 e 500 caracteres.")
        entry = self._get(entry_id, lock=True)
        if self.repository.reversals([entry_id]):
            raise BusinessConflict("Este lançamento já foi estornado.")
        reversal = FinancialEntry(
            id=uuid4(),
            clinic_id=entry.clinic_id,
            reverses_id=entry.id,
            author_id=actor.id,
            author_name=actor.name,
            reversal_reason=reason,
            **{
                field: getattr(entry, field)
                for field in (
                    "kind",
                    "description",
                    "category",
                    "amount_cents",
                    "occurred_on",
                    "payment_method",
                    "tutor_id",
                    "tutor_name",
                    "patient_id",
                    "patient_name",
                )
            },
        )
        try:
            self.repository.save(reversal)
        except IntegrityError:
            raise BusinessConflict("Este lançamento já foi estornado.") from None
        return self._read(entry, reversal)
