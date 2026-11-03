import re
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.tutors.models import Tutor


class TutorRepository(TenantRepository[Tutor]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Tutor)

    def locked(self, tutor_id: UUID) -> Tutor | None:
        return self.session.scalar(self._select().where(Tutor.id == tutor_id).with_for_update())

    def by_phone(self, phone: str) -> Sequence[Tutor]:
        return self.session.scalars(self._select().where(Tutor.phone == phone)).all()

    def list(self, search: str, limit: int, offset: int) -> tuple[Sequence[Tutor], int]:
        query = self._select()
        if search:
            digits = re.sub(r"[^0-9]", "", search)
            conditions = [Tutor.name.icontains(search, autoescape=True)]
            if digits:
                conditions.append(Tutor.phone.contains(digits, autoescape=True))
            query = query.where(or_(*conditions))
        total = self.session.scalar(select(func.count()).select_from(query.subquery())) or 0
        records = self.session.scalars(
            query.order_by(Tutor.name, Tutor.id).limit(limit).offset(offset)
        ).all()
        return records, total
