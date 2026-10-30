from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.modules.clinics.models import Role, User
from app.modules.clinics.repositories import ClinicRepository, UserRepository
from app.modules.clinics.schemas import UserUpdate
from app.modules.clinics.services import ClinicService, UserService


def actor(role: Role = Role.ADMIN) -> User:
    return User(id=uuid4(), clinic_id=uuid4(), name="Fictício", role=role, active=True)


def test_non_admin_is_denied_before_repository_access() -> None:
    repository = Mock(spec=UserRepository)
    service = UserService(repository, Mock(spec=ClinicRepository))
    with pytest.raises(AccessDenied):
        service.list(actor(Role.RECEPTION))
    repository.list.assert_not_called()


def test_missing_user_has_explicit_domain_error() -> None:
    repository = Mock(spec=UserRepository)
    repository.get.return_value = None
    with pytest.raises(ResourceNotFound):
        UserService(repository, Mock(spec=ClinicRepository)).get(actor(), uuid4())


@pytest.mark.parametrize("changes", [{"role": "veterinarian"}, {"crmv_state": "ZZ"}])
def test_invalid_professional_data_is_not_saved(changes: dict[str, str]) -> None:
    repository = Mock(spec=UserRepository)
    target = actor(Role.ASSISTANT)
    repository.get.return_value = target
    with pytest.raises(InvalidData):
        UserService(repository, Mock(spec=ClinicRepository)).update(
            actor(), target.id, UserUpdate.model_validate(changes)
        )
    repository.save.assert_not_called()


def test_last_administrator_is_preserved() -> None:
    repository = Mock(spec=UserRepository)
    target = actor()
    repository.get.return_value = target
    repository.count_active_admins.return_value = 1
    with pytest.raises(BusinessConflict):
        UserService(repository, Mock(spec=ClinicRepository)).update(
            target, target.id, UserUpdate(active=False)
        )
    repository.save.assert_not_called()


def test_inactive_clinic_is_denied() -> None:
    repository = Mock(spec=ClinicRepository)
    repository.current.return_value = None
    with pytest.raises(AccessDenied):
        ClinicService(repository).current()
