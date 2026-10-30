from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.db import TenantModel


@dataclass(frozen=True)
class ClinicContext:
    clinic_id: UUID


class TenantRepository[ModelT: TenantModel]:
    def __init__(self, session: Session, context: ClinicContext, model: type[ModelT]) -> None:
        self.session = session
        self.context = context
        self.model = model

    def _select(self, *, include_archived: bool = False) -> Select[ModelT]:
        query = select(self.model).where(self.model.clinic_id == self.context.clinic_id)
        return query if include_archived else query.where(self.model.deleted_at.is_(None))

    def get(self, entity_id: UUID, *, include_archived: bool = False) -> ModelT | None:
        query = self._select(include_archived=include_archived)
        return self.session.scalar(query.where(self.model.id == entity_id))

    def save(self, entity: ModelT) -> None:
        self.session.add(entity)
        self.session.flush()
