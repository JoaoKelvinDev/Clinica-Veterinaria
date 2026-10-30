from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AccessDenied, InvalidData
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.patients.repositories import LinkRepository, PatientRepository
from app.modules.patients.schemas import PatientCreate
from app.modules.patients.services import PatientService
from app.modules.tutors.models import Tutor
from app.modules.tutors.repositories import TutorRepository
from app.modules.tutors.schemas import ConsentInput, TutorCreate, TutorUpdate
from app.modules.tutors.services import TutorService, normalize_phone


def actor(role: Role = Role.ADMIN) -> User:
    return User(id=uuid4(), clinic_id=uuid4(), name="Fictício", role=role, active=True)


@pytest.mark.parametrize("raw", ["(86) 99999-9999", "+55 86 99999-9999", "86999999999"])
def test_phone_is_normalized_to_e164(raw: str) -> None:
    assert normalize_phone(raw) == "+5586999999999"


@pytest.mark.parametrize("raw", ["123", "abc", "+5586999999999 ext. 1"])
def test_invalid_phone_or_extension_is_rejected(raw: str) -> None:
    with pytest.raises(InvalidData):
        normalize_phone(raw)


def test_tutor_is_not_persisted_when_consent_has_no_phone() -> None:
    repository = Mock(spec=TutorRepository)
    repository.context = ClinicContext(uuid4())
    with pytest.raises(InvalidData):
        TutorService(repository).create(
            actor(),
            TutorCreate(
                name="Fictício", whatsapp_consent=ConsentInput(granted=True, source="Presencial")
            ),
        )
    repository.save.assert_not_called()


def test_phone_change_requires_new_consent() -> None:
    record = Tutor(
        name="Fictício",
        phone="+5586999999999",
        whatsapp_opt_in=True,
        whatsapp_opt_in_source="Presencial",
    )
    repository = Mock(spec=TutorRepository)
    repository.locked.return_value = record
    updated = TutorService(repository).update(actor(), uuid4(), TutorUpdate(phone="+5511961234567"))
    assert updated.whatsapp_opt_in is False
    assert updated.whatsapp_opt_out_at is not None


def test_patient_age_validation_happens_before_persistence() -> None:
    repository = Mock(spec=PatientRepository)
    repository.context = ClinicContext(uuid4())
    repository.microchip_exists.return_value = False
    service = PatientService(repository, Mock(spec=LinkRepository), Mock(spec=TutorService))
    with pytest.raises(InvalidData):
        service.create(
            actor(),
            PatientCreate(
                name="Fictício",
                species="Canina",
                birth_date=datetime.now(UTC).date() + timedelta(days=1),
            ),
        )
    repository.save.assert_not_called()


def test_reader_cannot_reach_mutation_repository() -> None:
    repository = Mock(spec=TutorRepository)
    with pytest.raises(AccessDenied):
        TutorService(repository).create(actor(Role.VETERINARIAN), TutorCreate(name="Fictício"))
    repository.save.assert_not_called()
