from datetime import UTC, date, datetime
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AccessDenied, BusinessConflict
from app.modules.clinics.models import Role, User
from app.modules.clinics.services import UserService
from app.modules.patients.services import PatientService
from app.modules.scheduling.models import Appointment, AppointmentStatus
from app.modules.scheduling.repositories import AppointmentRepository, EncounterRepository
from app.modules.scheduling.schemas import AppointmentCreate
from app.modules.scheduling.services import SchedulingService, day_bounds, require_veterinarian


def test_fortaleza_day_uses_utc_boundaries() -> None:
    assert day_bounds(date(2030, 1, 1)) == (
        datetime(2030, 1, 1, 3, tzinfo=UTC),
        datetime(2030, 1, 2, 3, tzinfo=UTC),
    )


def test_veterinarian_cannot_act_for_another_veterinarian() -> None:
    vet = User(id=uuid4(), role=Role.VETERINARIAN, active=True)
    with pytest.raises(AccessDenied):
        require_veterinarian(vet, uuid4())


def test_assistant_cannot_reach_booking_persistence() -> None:
    appointments = Mock(spec=AppointmentRepository)
    service = SchedulingService(
        appointments,
        Mock(spec=EncounterRepository),
        Mock(spec=PatientService),
        Mock(spec=UserService),
    )
    with pytest.raises(AccessDenied):
        service.create(
            User(role=Role.ASSISTANT, active=True),
            AppointmentCreate(
                patient_id=uuid4(),
                veterinarian_id=uuid4(),
                starts_at=datetime(2030, 1, 1, tzinfo=UTC),
                ends_at=datetime(2030, 1, 2, tzinfo=UTC),
                kind="Consulta",
            ),
        )
    appointments.save.assert_not_called()


def test_completed_appointment_cannot_be_cancelled() -> None:
    appointments = Mock(spec=AppointmentRepository)
    appointments.locked.return_value = Appointment(status="completed")
    service = SchedulingService(
        appointments,
        Mock(spec=EncounterRepository),
        Mock(spec=PatientService),
        Mock(spec=UserService),
    )
    with pytest.raises(BusinessConflict):
        service.change_status(
            User(role=Role.ADMIN, active=True), uuid4(), AppointmentStatus.CANCELLED
        )
    appointments.save.assert_not_called()
