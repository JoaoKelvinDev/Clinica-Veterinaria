from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.errors import BusinessConflict, InvalidData, ResourceNotFound
from app.core.permissions import require_registry_writer
from app.modules.clinics.models import User
from app.modules.patients.models import Patient, TutorPatient
from app.modules.patients.repositories import LinkRepository, PatientRepository
from app.modules.patients.schemas import (
    PatientCreate,
    PatientPage,
    PatientRead,
    PatientUpdate,
    TutorLinkRead,
)
from app.modules.tutors.schemas import TutorRead
from app.modules.tutors.services import TutorService


class PatientService:
    def __init__(
        self, repository: PatientRepository, links: LinkRepository, tutors: TutorService
    ) -> None:
        self.repository = repository
        self.links = links
        self.tutors = tutors

    def get(self, patient_id: UUID, *, lock: bool = False) -> Patient:
        patient = self.repository.locked(patient_id) if lock else self.repository.get(patient_id)
        if patient is None:
            raise ResourceNotFound("Paciente não encontrado.")
        return patient

    def search(self, search: str, limit: int, offset: int) -> PatientPage:
        items, total = self.repository.list(search.strip(), limit, offset)
        return PatientPage(items=[PatientRead.model_validate(item) for item in items], total=total)

    def _validate(self, patient: Patient) -> None:
        if patient.birth_date and patient.birth_date > datetime.now(UTC).date():
            raise InvalidData("A data de nascimento não pode estar no futuro.")
        if patient.birth_date and patient.estimated_age_months is not None:
            raise InvalidData("Informe a data de nascimento ou a idade estimada, não as duas.")
        patient.microchip = patient.microchip.strip().upper() if patient.microchip else None
        if patient.microchip and self.repository.microchip_exists(patient.microchip, patient.id):
            raise BusinessConflict("Microchip já cadastrado nesta clínica.")

    def _save(self, patient: Patient) -> None:
        self._validate(patient)
        try:
            self.repository.save(patient)
        except IntegrityError:
            raise BusinessConflict(
                "Os dados do paciente conflitam com um cadastro existente."
            ) from None

    def create(self, actor: User, values: PatientCreate) -> Patient:
        require_registry_writer(actor)
        patient = Patient(
            id=uuid4(), clinic_id=self.repository.context.clinic_id, **values.model_dump()
        )
        self._save(patient)
        return patient

    def update(self, actor: User, patient_id: UUID, changes: PatientUpdate) -> Patient:
        require_registry_writer(actor)
        patient = self.get(patient_id, lock=True)
        for field in changes.model_fields_set:
            setattr(patient, field, getattr(changes, field))
        self._save(patient)
        return patient

    def archive(self, actor: User, patient_id: UUID) -> None:
        require_registry_writer(actor)
        patient = self.get(patient_id, lock=True)
        patient.deleted_at = datetime.now(UTC)
        self.repository.save(patient)

    def list_tutors(self, patient_id: UUID) -> list[TutorLinkRead]:
        self.get(patient_id)
        return [
            TutorLinkRead(
                id=link.id,
                is_primary=link.is_primary,
                tutor=TutorRead.model_validate(
                    self.tutors.get(link.tutor_id, include_archived=True)
                ),
            )
            for link in self.links.list(patient_id)
        ]

    def link(self, actor: User, patient_id: UUID, tutor_id: UUID, is_primary: bool) -> TutorPatient:
        require_registry_writer(actor)
        self.get(patient_id, lock=True)
        self.tutors.get(tutor_id)
        current = self.links.list(patient_id)
        principal = is_primary or not current
        if principal:
            self.links.clear_primary(patient_id)
        link = self.links.pair(patient_id, tutor_id)
        if link is None:
            link = TutorPatient(
                clinic_id=self.repository.context.clinic_id,
                patient_id=patient_id,
                tutor_id=tutor_id,
                is_primary=principal,
            )
        else:
            link.deleted_at = None
            link.is_primary = principal or link.is_primary
        self.links.save(link)
        return link

    def unlink(self, actor: User, patient_id: UUID, tutor_id: UUID) -> None:
        require_registry_writer(actor)
        self.get(patient_id, lock=True)
        link = self.links.pair(patient_id, tutor_id)
        if link is None or link.deleted_at is not None:
            raise ResourceNotFound("Vínculo não encontrado.")
        link.deleted_at = datetime.now(UTC)
        link.is_primary = False
        self.links.save(link)
