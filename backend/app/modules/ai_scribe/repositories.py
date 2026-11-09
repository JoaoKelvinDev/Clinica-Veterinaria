from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.ai_scribe.models import AiDraft


class DraftRepository(TenantRepository[AiDraft]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, AiDraft)

    def locked(self, draft_id: UUID) -> AiDraft | None:
        return self.session.scalar(self._select().where(AiDraft.id == draft_id).with_for_update())

    def for_patient(self, patient_id: UUID) -> Sequence[AiDraft]:
        return self.session.scalars(
            self._select()
            .where(AiDraft.patient_id == patient_id)
            .order_by(AiDraft.created_at.desc(), AiDraft.id)
        ).all()
