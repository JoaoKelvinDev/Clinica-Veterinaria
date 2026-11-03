from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.core.permissions import require_registry_writer
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.clinics.repositories import ClinicRepository, UserRepository
from app.modules.clinics.services import UserService
from app.modules.patients.services import PatientService
from app.modules.scheduling.models import Appointment, AppointmentStatus, Encounter
from app.modules.scheduling.repositories import AppointmentRepository, EncounterRepository
from app.modules.scheduling.schemas import (
    AppointmentCreate,
    AppointmentPage,
    AppointmentRead,
    AppointmentUpdate,
    EncounterPage,
    EncounterRead,
)

TIMEZONE = ZoneInfo("America/Fortaleza")
EDITABLE = {"scheduled", "confirmed"}
DEADLOCK = "40P01"


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, TIMEZONE)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def require_veterinarian(actor: User, veterinarian_id: UUID) -> None:
    if (
        not actor.active
        or actor.deleted_at is not None
        or actor.role != Role.VETERINARIAN
        or actor.id != veterinarian_id
    ):
        raise AccessDenied(
            "Somente o veterinário responsável pode iniciar ou concluir este atendimento."
        )


class SchedulingService:
    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "SchedulingService":
        return cls(
            AppointmentRepository(session, context),
            EncounterRepository(session, context),
            PatientService.for_clinic(session, context),
            UserService(UserRepository(session, context), ClinicRepository(session, context)),
        )

    def __init__(
        self,
        appointments: AppointmentRepository,
        encounters: EncounterRepository,
        patients: PatientService,
        users: UserService,
    ) -> None:
        self.appointments = appointments
        self.encounters = encounters
        self.patients = patients
        self.users = users

    def get(self, appointment_id: UUID, *, lock: bool = False) -> Appointment:
        item = (
            self.appointments.locked(appointment_id)
            if lock
            else self.appointments.get(appointment_id)
        )
        if item is None and lock:
            # RLS de UPDATE oculta linhas encerradas de SELECT FOR UPDATE.
            item = self.appointments.get(appointment_id)
        if item is None:
            raise ResourceNotFound("Agendamento não encontrado.")
        return item

    def get_encounter(self, encounter_id: UUID, *, lock: bool = False) -> Encounter:
        item = self.encounters.locked(encounter_id) if lock else self.encounters.get(encounter_id)
        if item is None and lock:
            item = self.encounters.fresh(encounter_id)
        if item is None:
            raise ResourceNotFound("Atendimento não encontrado.")
        return item

    def appointment_read(self, item: Appointment) -> AppointmentRead:
        patient = self.patients.get(item.patient_id, include_archived=True)
        vet = self.users.veterinarian(item.veterinarian_id, require_active=False)
        encounter = self.encounters.for_appointment(item.id)
        return AppointmentRead(
            id=item.id,
            clinic_id=item.clinic_id,
            patient_id=item.patient_id,
            patient_name=patient.name,
            veterinarian_id=item.veterinarian_id,
            veterinarian_name=vet.name,
            starts_at=item.starts_at,
            ends_at=item.ends_at,
            kind=item.kind,
            status=AppointmentStatus(item.status),
            encounter_id=encounter.id if encounter else None,
        )

    def encounter_read(self, item: Encounter) -> EncounterRead:
        patient = self.patients.get(item.patient_id, include_archived=True)
        vet = self.users.veterinarian(item.veterinarian_id, require_active=False)
        return EncounterRead(
            id=item.id,
            clinic_id=item.clinic_id,
            patient_id=item.patient_id,
            patient_name=patient.name,
            veterinarian_id=item.veterinarian_id,
            veterinarian_name=vet.name,
            appointment_id=item.appointment_id,
            started_at=item.started_at,
            completed_at=item.completed_at,
        )

    def search(
        self, day: date, veterinarian_id: UUID | None, limit: int, offset: int
    ) -> AppointmentPage:
        items, total = self.appointments.page(*day_bounds(day), veterinarian_id, limit, offset)
        return AppointmentPage(items=[self.appointment_read(item) for item in items], total=total)

    def patient_encounters(self, patient_id: UUID) -> list[EncounterRead]:
        return [self.encounter_read(item) for item in self.encounters.for_patient(patient_id)]

    def search_encounters(
        self, day: date, veterinarian_id: UUID | None, limit: int, offset: int
    ) -> EncounterPage:
        items, total = self.encounters.page(*day_bounds(day), veterinarian_id, limit, offset)
        return EncounterPage(items=[self.encounter_read(item) for item in items], total=total)

    def _save_appointment(self, item: Appointment) -> None:
        item.starts_at = item.starts_at.astimezone(UTC)
        item.ends_at = item.ends_at.astimezone(UTC)
        if item.ends_at <= item.starts_at:
            raise InvalidData("O fim deve ser posterior ao início do agendamento.")
        with self.appointments.session.no_autoflush:
            self.patients.get(item.patient_id)
            self.users.veterinarian(item.veterinarian_id)
            if self.appointments.overlaps(item):
                raise BusinessConflict("O veterinário já possui um agendamento nesse intervalo.")
        try:
            self.appointments.save(item)
        except (IntegrityError, OperationalError) as error:
            # Duas reservas simultâneas do mesmo horário podem terminar em deadlock na
            # restrição de exclusão; para quem agenda, é o mesmo conflito de horário.
            if isinstance(error, OperationalError) and (
                getattr(error.orig, "sqlstate", None) != DEADLOCK
            ):
                raise
            raise BusinessConflict(
                "Não foi possível reservar esse horário. "
                "Atualize a agenda e escolha outro intervalo."
            ) from None

    def create(self, actor: User, values: AppointmentCreate) -> Appointment:
        require_registry_writer(actor)
        item = Appointment(
            id=uuid4(),
            clinic_id=self.appointments.context.clinic_id,
            status="scheduled",
            **values.model_dump(),
        )
        self._save_appointment(item)
        return item

    def update(self, actor: User, appointment_id: UUID, changes: AppointmentUpdate) -> Appointment:
        require_registry_writer(actor)
        item = self.get(appointment_id, lock=True)
        if item.status not in EDITABLE:
            raise BusinessConflict("Somente agendamentos ainda não iniciados podem ser alterados.")
        for field in changes.model_fields_set:
            setattr(item, field, getattr(changes, field))
        # Reagendamento precisa de uma nova confirmação do horário.
        item.status = "scheduled"
        self._save_appointment(item)
        return item

    def change_status(
        self, actor: User, appointment_id: UUID, status: AppointmentStatus
    ) -> Appointment:
        require_registry_writer(actor)
        item = self.get(appointment_id, lock=True)
        if item.status not in EDITABLE or status not in {
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        }:
            raise BusinessConflict(
                "Essa mudança de situação não é permitida. "
                "Use iniciar ou concluir para atendimentos."
            )
        item.status = status.value
        self.appointments.save(item)
        return item

    def start(self, actor: User, appointment_id: UUID) -> Encounter:
        item = self.get(appointment_id, lock=True)
        require_veterinarian(actor, item.veterinarian_id)
        if item.status == "in_progress":
            existing = self.encounters.for_appointment(item.id)
            if existing is not None:
                return existing
        if item.status not in EDITABLE:
            raise BusinessConflict("Este agendamento não pode ser iniciado.")
        self.patients.get(item.patient_id)
        self.users.veterinarian(item.veterinarian_id)
        item.status = "in_progress"
        self.appointments.save(item)
        encounter = Encounter(
            clinic_id=item.clinic_id,
            patient_id=item.patient_id,
            veterinarian_id=actor.id,
            appointment_id=item.id,
            started_at=datetime.now(UTC),
        )
        self.encounters.save(encounter)
        return encounter

    def start_walk_in(self, actor: User, patient_id: UUID) -> Encounter:
        require_veterinarian(actor, actor.id)
        self.patients.get(patient_id)
        encounter = Encounter(
            clinic_id=self.encounters.context.clinic_id,
            patient_id=patient_id,
            veterinarian_id=actor.id,
            started_at=datetime.now(UTC),
        )
        self.encounters.save(encounter)
        return encounter

    def complete(self, actor: User, encounter_id: UUID) -> Encounter:
        # A mesma ordem de locks de start evita um ciclo entre agendamento e atendimento.
        current = self.get_encounter(encounter_id)
        appointment = (
            self.get(current.appointment_id, lock=True) if current.appointment_id else None
        )
        item = self.get_encounter(encounter_id, lock=True)
        require_veterinarian(actor, item.veterinarian_id)
        if item.completed_at is not None:
            return item
        if appointment is not None:
            if appointment.status != "in_progress":
                raise BusinessConflict("O agendamento não está em atendimento.")
            appointment.status = "completed"
            self.appointments.save(appointment)
        item.completed_at = datetime.now(UTC)
        self.encounters.save(item)
        return item
