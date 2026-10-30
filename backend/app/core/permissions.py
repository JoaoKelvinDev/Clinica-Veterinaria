from app.core.errors import AccessDenied
from app.modules.clinics.models import Role, User


def require_registry_writer(actor: User) -> None:
    if (
        not actor.active
        or actor.deleted_at is not None
        or actor.role not in {Role.ADMIN, Role.RECEPTION}
    ):
        raise AccessDenied("Somente administradores e recepção podem alterar os cadastros.")
