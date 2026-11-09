from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.quotes.models import Quote, QuoteItem
from app.modules.quotes.repositories import QuoteItemRepository, QuoteRepository
from app.modules.quotes.schemas import (
    MAX_CENTS,
    EncounterOption,
    QuoteCreate,
    QuoteDecision,
    QuoteEdit,
    QuoteItemInput,
    QuoteItemRead,
    QuoteOptions,
    QuotePage,
    QuoteRead,
    QuoteSummary,
    TutorOption,
)
from app.modules.scheduling.services import SchedulingService

WRITERS = {Role.ADMIN, Role.VETERINARIAN, Role.RECEPTION}
TIMEZONE = ZoneInfo("America/Fortaleza")


def require_writer(actor: User) -> None:
    if not actor.active or actor.deleted_at is not None or actor.role not in WRITERS:
        raise AccessDenied("Somente administradores, veterinários e recepção alteram orçamentos.")


def calculate(items: list[QuoteItemInput], discount: int) -> tuple[int, int]:
    subtotal = 0
    for item in items:
        line = int(
            (item.quantity * item.unit_price_cents).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )
        if line > MAX_CENTS:
            raise InvalidData("O valor de um item ultrapassa o limite permitido.")
        subtotal += line
    if subtotal > MAX_CENTS:
        raise InvalidData("O subtotal ultrapassa o limite permitido.")
    if discount > subtotal:
        raise InvalidData("O desconto não pode superar o subtotal.")
    return subtotal, subtotal - discount


class QuoteService:
    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "QuoteService":
        return cls(
            QuoteRepository(session, context),
            QuoteItemRepository(session, context),
            SchedulingService.for_clinic(session, context),
        )

    def __init__(
        self, quotes: QuoteRepository, items: QuoteItemRepository, scheduling: SchedulingService
    ) -> None:
        self.quotes, self.items, self.scheduling = quotes, items, scheduling

    def today(self) -> date:
        return datetime.now(TIMEZONE).date()

    def status(self, quote: Quote) -> str:
        if (
            quote.status == "sent"
            and quote.valid_until is not None
            and quote.valid_until < self.today()
        ):
            return "expired"
        return quote.status

    def _summary(self, quote: Quote) -> QuoteSummary:
        return QuoteSummary.model_validate(
            {
                **{
                    key: getattr(quote, key) for key in QuoteSummary.model_fields if key != "status"
                },
                "status": self.status(quote),
            }
        )

    def _read(self, quote: Quote) -> QuoteRead:
        return QuoteRead(
            **self._summary(quote).model_dump(),
            items=[QuoteItemRead.model_validate(item) for item in self.items.for_quote(quote.id)],
        )

    def get(self, quote_id: UUID) -> QuoteRead:
        quote = self.quotes.get(quote_id)
        if quote is None:
            raise ResourceNotFound("Orçamento não encontrado.")
        return self._read(quote)

    def list(self, query: str, status: str | None, limit: int, offset: int) -> QuotePage:
        quotes, total = self.quotes.page(query.strip(), status, self.today(), limit, offset)
        return QuotePage(items=[self._summary(quote) for quote in quotes], total=total)

    def options(self, patient_id: UUID) -> QuoteOptions:
        self.scheduling.patients.get(patient_id)
        tutors = self.scheduling.patients.list_tutors(patient_id)
        return QuoteOptions(
            tutors=[
                TutorOption(id=link.tutor.id, name=link.tutor.name, is_primary=link.is_primary)
                for link in tutors
                if link.tutor.deleted_at is None
            ],
            encounters=[
                EncounterOption(
                    id=item.id, started_at=item.started_at, veterinarian_name=item.veterinarian_name
                )
                for item in self.scheduling.patient_encounters(patient_id)
            ],
        )

    def _identity(self, values: QuoteCreate) -> tuple[str, str]:
        patient = self.scheduling.patients.get(values.patient_id)
        tutors = self.scheduling.patients.list_tutors(patient.id)
        tutor = next(
            (
                link.tutor
                for link in tutors
                if link.tutor.id == values.tutor_id and link.tutor.deleted_at is None
            ),
            None,
        )
        if tutor is None:
            raise InvalidData("Escolha um tutor ativo vinculado ao paciente.")
        if values.encounter_id is not None:
            encounter = self.scheduling.get_encounter(values.encounter_id)
            if encounter.patient_id != patient.id:
                raise InvalidData("O atendimento informado é de outro paciente.")
        if values.valid_until is not None and values.valid_until < self.today():
            raise InvalidData("A validade não pode estar no passado.")
        return patient.name, tutor.name

    def _write(self, quote: Quote, values: QuoteCreate) -> None:
        # A edição já alterou a versão em memória; consultas de validação não podem
        # gravar esse estado intermediário antes do conteúdo final do orçamento.
        with self.quotes.session.no_autoflush:
            patient_name, tutor_name = self._identity(values)
        subtotal, total = calculate(values.items, values.discount_cents)
        for field in ("patient_id", "tutor_id", "encounter_id", "valid_until", "discount_cents"):
            setattr(quote, field, getattr(values, field))
        quote.patient_name, quote.tutor_name = patient_name, tutor_name
        quote.subtotal_cents, quote.total_cents = subtotal, total
        self.quotes.save(quote)
        self.items.replace(
            quote.id,
            [
                QuoteItem(
                    clinic_id=self.items.context.clinic_id,
                    quote_id=quote.id,
                    position=index,
                    **item.model_dump(),
                )
                for index, item in enumerate(values.items, 1)
            ],
        )

    def create(
        self, actor: User, values: QuoteCreate, *, source_quote_id: UUID | None = None
    ) -> QuoteRead:
        require_writer(actor)
        quote = Quote(
            clinic_id=self.quotes.context.clinic_id,
            created_by=actor.id,
            updated_by=actor.id,
            source_quote_id=source_quote_id,
        )
        self._write(quote, values)
        return self._read(quote)

    def _locked(self, actor: User, quote_id: UUID, expected_version: int) -> Quote:
        require_writer(actor)
        quote = self.quotes.locked(quote_id)
        if quote is None:
            raise ResourceNotFound("Orçamento não encontrado.")
        if quote.version != expected_version:
            raise BusinessConflict("O orçamento mudou. Atualize a tela antes de continuar.")
        return quote

    def edit(self, actor: User, quote_id: UUID, values: QuoteEdit) -> QuoteRead:
        quote = self._locked(actor, quote_id, values.expected_version)
        if quote.status != "draft":
            raise BusinessConflict("Somente rascunhos podem ser editados. Crie uma revisão.")
        quote.version += 1
        quote.updated_by = actor.id
        self._write(quote, values)
        return self._read(quote)

    def present(self, actor: User, quote_id: UUID, expected_version: int) -> QuoteRead:
        quote = self._locked(actor, quote_id, expected_version)
        if quote.status != "draft":
            raise BusinessConflict("Somente rascunhos podem ser apresentados.")
        # A foto dos nomes é atualizada na apresentação e preservada a partir daí.
        values = QuoteCreate(
            patient_id=quote.patient_id,
            tutor_id=quote.tutor_id,
            encounter_id=quote.encounter_id,
            valid_until=quote.valid_until,
            discount_cents=quote.discount_cents,
            items=[
                QuoteItemInput.model_validate(item, from_attributes=True)
                for item in self.items.for_quote(quote.id)
            ],
        )
        quote.patient_name, quote.tutor_name = self._identity(values)
        quote.status, quote.presented_by, quote.presented_at = "sent", actor.id, datetime.now(UTC)
        quote.version += 1
        quote.updated_by = actor.id
        self.quotes.save(quote)
        return self._read(quote)

    def decide(
        self, actor: User, quote_id: UUID, values: QuoteDecision, *, approve: bool
    ) -> QuoteRead:
        quote = self._locked(actor, quote_id, values.expected_version)
        if self.status(quote) != "sent":
            raise BusinessConflict(
                "Somente orçamentos enviados e dentro da validade podem receber decisão."
            )
        quote.status = "approved" if approve else "rejected"
        quote.decision_source, quote.decision_note = values.source, values.note
        quote.decision_at, quote.decision_by = datetime.now(UTC), actor.id
        quote.version += 1
        quote.updated_by = actor.id
        self.quotes.save(quote)
        return self._read(quote)

    def revise(self, actor: User, quote_id: UUID, expected_version: int) -> QuoteRead:
        quote = self._locked(actor, quote_id, expected_version)
        if quote.status == "draft":
            raise BusinessConflict("Edite o rascunho existente antes de apresentá-lo.")
        values = QuoteCreate(
            patient_id=quote.patient_id,
            tutor_id=quote.tutor_id,
            encounter_id=quote.encounter_id,
            valid_until=quote.valid_until
            if quote.valid_until is None or quote.valid_until >= self.today()
            else None,
            discount_cents=quote.discount_cents,
            items=[
                QuoteItemInput.model_validate(item, from_attributes=True)
                for item in self.items.for_quote(quote.id)
            ],
        )
        return self.create(actor, values, source_quote_id=quote.id)
