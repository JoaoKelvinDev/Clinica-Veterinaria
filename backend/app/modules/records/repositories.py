from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, aliased

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.records.models import (
    AuditLog,
    PatientDocument,
    RecordEntry,
    VaccineRecord,
    WeightRecord,
)

type Superseding = RecordEntry | WeightRecord | VaccineRecord | PatientDocument


class AppendOnlyRepository[ModelT: Superseding](TenantRepository[ModelT]):
    def current_for_patient(self, patient_id: UUID) -> Sequence[ModelT]:
        """Versões vigentes: as que nenhum outro registro substituiu."""
        newer = aliased(self.model)
        superseded = select(newer.id).where(
            newer.clinic_id == self.context.clinic_id, newer.supersedes_id == self.model.id
        )
        return self.session.scalars(
            self._select()
            .where(self.model.patient_id == patient_id, ~superseded.exists())
            .order_by(self.model.created_at.desc(), self.model.id)
        ).all()

    def is_superseded(self, entity_id: UUID) -> bool:
        return (
            self.session.scalar(
                self._select().where(self.model.supersedes_id == entity_id).limit(1)
            )
            is not None
        )


class RecordEntryRepository(AppendOnlyRepository[RecordEntry]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, RecordEntry)

    def versions(self, root_id: UUID) -> Sequence[RecordEntry]:
        return self.session.scalars(
            self._select().where(RecordEntry.root_id == root_id).order_by(RecordEntry.version)
        ).all()


class WeightRepository(AppendOnlyRepository[WeightRecord]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, WeightRecord)


class VaccineRepository(AppendOnlyRepository[VaccineRecord]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, VaccineRecord)


class DocumentRepository(AppendOnlyRepository[PatientDocument]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, PatientDocument)

    def versions(self, root_id: UUID) -> Sequence[PatientDocument]:
        return self.session.scalars(
            self._select()
            .where(PatientDocument.root_id == root_id)
            .order_by(PatientDocument.version)
        ).all()


class AuditRepository(TenantRepository[AuditLog]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, AuditLog)

    def add(
        self, actor_id: UUID, action: str, entity: str, entity_id: UUID, patient_id: UUID
    ) -> None:
        # Sem RETURNING: somente administradores podem ler a auditoria pela RLS.
        self.session.execute(
            insert(AuditLog).values(
                id=uuid4(),
                clinic_id=self.context.clinic_id,
                actor_id=actor_id,
                action=action,
                entity=entity,
                entity_id=entity_id,
                patient_id=patient_id,
            )
        )
