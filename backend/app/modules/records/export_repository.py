from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.records.export_models import RecordExport


class ExportRepository(TenantRepository[RecordExport]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, RecordExport)

    def page(self, patient_id: UUID, limit: int, offset: int) -> tuple[Sequence[RecordExport], int]:
        statement = self._select().where(RecordExport.patient_id == patient_id)
        total = self.session.scalar(statement.with_only_columns(func.count())) or 0
        return self.session.scalars(
            statement.order_by(RecordExport.created_at.desc(), RecordExport.id)
            .limit(limit)
            .offset(offset)
        ).all(), total
