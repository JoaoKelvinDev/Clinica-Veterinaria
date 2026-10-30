from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.repositories import ClinicContext, TenantRepository
from app.modules.clinics.models import Clinic, Role, User


class IdentityRepository:
    """Resolve somente a identidade autenticada antes de conhecer sua clínica."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_auth_id(self, auth_id: UUID) -> User | None:
        return self.session.scalar(select(User).where(User.auth_id == auth_id))


class ClinicRepository(TenantRepository[Clinic]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, Clinic)

    def current(self, *, lock: bool = False) -> Clinic | None:
        query = self._select()
        if lock:
            query = query.with_for_update()
        return self.session.scalar(query)

    def save(self, clinic: Clinic) -> None:
        self.session.add(clinic)
        self.session.flush()


class UserRepository(TenantRepository[User]):
    def __init__(self, session: Session, context: ClinicContext) -> None:
        super().__init__(session, context, User)

    def list(self) -> Sequence[User]:
        return self.session.scalars(self._select().order_by(User.name, User.id)).all()

    def count_active_admins(self) -> int:
        query = self._select().where(User.role == Role.ADMIN, User.active.is_(True)).subquery()
        return self.session.scalar(select(func.count()).select_from(query)) or 0

    def veterinarians(self) -> Sequence[User]:
        return self.session.scalars(
            self._select()
            .where(User.role == Role.VETERINARIAN, User.active.is_(True))
            .order_by(User.name, User.id)
        ).all()

    def save(self, user: User) -> None:
        self.session.add(user)
        self.session.flush()
