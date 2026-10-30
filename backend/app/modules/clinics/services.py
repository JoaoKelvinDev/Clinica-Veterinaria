from collections.abc import Sequence
from uuid import UUID

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.modules.clinics.models import Clinic, Role, User
from app.modules.clinics.repositories import ClinicRepository, UserRepository
from app.modules.clinics.schemas import UserUpdate

BRAZIL_STATES = frozenset(
    "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
)


def require_admin(actor: User) -> None:
    if not actor.active or actor.deleted_at is not None or actor.role != Role.ADMIN:
        raise AccessDenied("Somente administradores podem executar esta ação.")


class ClinicService:
    def __init__(self, repository: ClinicRepository) -> None:
        self.repository = repository

    def current(self) -> Clinic:
        clinic = self.repository.current()
        if clinic is None:
            raise AccessDenied("A clínica não está disponível para este usuário.")
        return clinic

    def rename(self, actor: User, name: str) -> Clinic:
        require_admin(actor)
        clinic = self.current()
        clinic.name = name
        self.repository.save(clinic)
        return clinic


class UserService:
    def __init__(self, repository: UserRepository, clinics: ClinicRepository) -> None:
        self.repository = repository
        self.clinics = clinics

    def list(self, actor: User) -> Sequence[User]:
        require_admin(actor)
        return self.repository.list()

    def get(self, actor: User, user_id: UUID) -> User:
        require_admin(actor)
        user = self.repository.get(user_id)
        if user is None:
            raise ResourceNotFound("Usuário não encontrado.")
        return user

    def update(self, actor: User, user_id: UUID, changes: UserUpdate) -> User:
        require_admin(actor)
        # Serializa alterações para impedir perda concorrente do último administrador.
        if self.clinics.current(lock=True) is None:
            raise AccessDenied("A clínica não está disponível.")
        user = self.get(actor, user_id)
        role = changes.role if changes.role is not None else user.role
        active = changes.active if changes.active is not None else user.active
        crmv = changes.crmv if "crmv" in changes.model_fields_set else user.crmv
        state = changes.crmv_state if "crmv_state" in changes.model_fields_set else user.crmv_state
        if state is not None and state not in BRAZIL_STATES:
            raise InvalidData("Informe uma UF válida para o CRMV.")
        if role == Role.VETERINARIAN and (not crmv or not state):
            raise InvalidData("Veterinários precisam de CRMV e UF.")
        if user.role == Role.ADMIN and user.active and (role != Role.ADMIN or not active):
            if self.repository.count_active_admins() <= 1:
                raise BusinessConflict(
                    "A clínica precisa manter pelo menos um administrador ativo."
                )
        if changes.name is not None:
            user.name = changes.name
        user.role, user.active, user.crmv, user.crmv_state = role, active, crmv, state
        self.repository.save(user)
        return user
