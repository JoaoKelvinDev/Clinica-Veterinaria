from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AccessDenied, BusinessConflict, InvalidData, ResourceNotFound
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.clinics.repositories import ClinicRepository
from app.modules.clinics.services import ClinicService
from app.modules.records.models import RecordEntry, VaccineRecord, WeightRecord
from app.modules.records.repositories import (
    AppendOnlyRepository,
    AuditRepository,
    DocumentRepository,
    RecordEntryRepository,
    Superseding,
    VaccineRepository,
    WeightRepository,
)
from app.modules.records.schemas import (
    DocumentRead,
    PatientRecord,
    RecordEntryCreate,
    RecordEntryRead,
    TimelineEncounter,
    VaccineCreate,
    VaccineRead,
    WeightCreate,
    WeightRead,
)
from app.modules.scheduling.services import SchedulingService

TIMEZONE = ZoneInfo("America/Fortaleza")
CLINICAL_READERS = {Role.ADMIN, Role.VETERINARIAN, Role.ASSISTANT}


def _active(actor: User) -> bool:
    return actor.active and actor.deleted_at is None


def require_clinical_reader(actor: User) -> None:
    # A recepção não acessa conteúdo clínico detalhado (AGENTS.md, seção 6.4).
    if not _active(actor) or actor.role not in CLINICAL_READERS:
        raise AccessDenied("Seu papel não permite consultar o conteúdo do prontuário.")


def require_clinician(actor: User) -> str:
    """Retorna a identificação profissional gravada junto ao registro."""
    if not _active(actor) or actor.role != Role.VETERINARIAN:
        raise AccessDenied("Somente veterinários registram no prontuário.")
    if not actor.crmv or not actor.crmv_state:
        raise InvalidData("Cadastre o CRMV e a UF do veterinário antes de registrar.")
    return f"CRMV-{actor.crmv_state} {actor.crmv}"


def require_weight_writer(actor: User) -> None:
    if not _active(actor) or actor.role not in {Role.VETERINARIAN, Role.ASSISTANT}:
        raise AccessDenied("Somente veterinários e auxiliares registram o peso.")


class RecordService:
    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "RecordService":
        return cls(
            RecordEntryRepository(session, context),
            WeightRepository(session, context),
            VaccineRepository(session, context),
            AuditRepository(session, context),
            SchedulingService.for_clinic(session, context),
            ClinicService(ClinicRepository(session, context)),
            DocumentRepository(session, context),
        )

    def __init__(
        self,
        entries: RecordEntryRepository,
        weights: WeightRepository,
        vaccines: VaccineRepository,
        audit: AuditRepository,
        scheduling: SchedulingService,
        clinics: ClinicService,
        documents: DocumentRepository,
    ) -> None:
        self.entries = entries
        self.weights = weights
        self.vaccines = vaccines
        self.audit = audit
        self.scheduling = scheduling
        self.clinics = clinics
        self.documents = documents

    def record(self, actor: User, patient_id: UUID) -> PatientRecord:
        self.scheduling.patients.get(patient_id, include_archived=True)
        encounters = [
            TimelineEncounter(
                id=item.id,
                started_at=item.started_at,
                completed_at=item.completed_at,
                veterinarian_name=item.veterinarian_name,
                appointment_id=item.appointment_id,
            )
            for item in self.scheduling.patient_encounters(patient_id)
        ]
        if actor.role not in CLINICAL_READERS or not _active(actor):
            return PatientRecord(
                patient_id=patient_id,
                clinical_access=False,
                encounters=encounters,
                entries=[],
                weights=[],
                vaccines=[],
                documents=[],
            )
        self.audit.add(actor.id, "read", "patient_record", patient_id, patient_id)
        return PatientRecord(
            patient_id=patient_id,
            clinical_access=True,
            encounters=encounters,
            entries=[
                RecordEntryRead.model_validate(item, from_attributes=True)
                for item in self.entries.current_for_patient(patient_id)
            ],
            weights=[
                WeightRead.model_validate(item, from_attributes=True)
                for item in self.weights.current_for_patient(patient_id)
            ],
            vaccines=[
                VaccineRead.model_validate(item, from_attributes=True)
                for item in self.vaccines.current_for_patient(patient_id)
            ],
            documents=[
                DocumentRead.model_validate(item, from_attributes=True)
                for item in self.documents.current_for_patient(patient_id)
            ],
        )

    def versions(self, actor: User, entry_id: UUID) -> list[RecordEntryRead]:
        require_clinical_reader(actor)
        entry = self.entries.get(entry_id)
        if entry is None:
            raise ResourceNotFound("Registro do prontuário não encontrado.")
        self.audit.add(actor.id, "read", "record_entry", entry.root_id, entry.patient_id)
        return [
            RecordEntryRead.model_validate(item, from_attributes=True)
            for item in self.entries.versions(entry.root_id)
        ]

    def _previous[ModelT: Superseding](
        self,
        repository: AppendOnlyRepository[ModelT],
        actor: User,
        patient_id: UUID,
        supersedes_id: UUID,
    ) -> ModelT:
        previous = repository.get(supersedes_id)
        if previous is None or previous.patient_id != patient_id:
            raise ResourceNotFound("Registro a corrigir não encontrado para este paciente.")
        if previous.author_id != actor.id:
            raise AccessDenied("Somente o autor pode corrigir o próprio registro.")
        if repository.is_superseded(previous.id):
            raise BusinessConflict("Este registro já foi corrigido. Corrija a versão mais recente.")
        return previous

    def _save[ModelT: Superseding](
        self, repository: AppendOnlyRepository[ModelT], item: ModelT
    ) -> None:
        try:
            repository.save(item)
        except IntegrityError:
            raise BusinessConflict(
                "Outro registro foi salvo ao mesmo tempo. Atualize o prontuário e tente de novo."
            ) from None

    def add_entry(
        self, actor: User, encounter_id: UUID, values: RecordEntryCreate
    ) -> RecordEntryRead:
        crmv = require_clinician(actor)
        encounter = self.scheduling.get_encounter(encounter_id)
        content = values.model_dump(exclude={"supersedes_id", "correction_reason", "location"})
        entry_id = uuid4()
        if values.supersedes_id is None:
            root_id, version = entry_id, 1
        else:
            previous = self._previous(
                self.entries, actor, encounter.patient_id, values.supersedes_id
            )
            if previous.encounter_id != encounter.id:
                raise InvalidData("A correção deve pertencer ao mesmo atendimento.")
            root_id, version = previous.root_id, previous.version + 1
        entry = RecordEntry(
            id=entry_id,
            clinic_id=self.entries.context.clinic_id,
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            root_id=root_id,
            version=version,
            supersedes_id=values.supersedes_id,
            correction_reason=values.correction_reason,
            author_id=actor.id,
            author_name=actor.name,
            author_crmv=crmv,
            location=values.location or self.clinics.current().name,
            **content,
        )
        self._save(self.entries, entry)
        action = "create" if version == 1 else "correct"
        self.audit.add(actor.id, action, "record_entry", entry.id, entry.patient_id)
        return RecordEntryRead.model_validate(entry, from_attributes=True)

    def add_weight(self, actor: User, patient_id: UUID, values: WeightCreate) -> WeightRead:
        require_weight_writer(actor)
        self.scheduling.patients.get(patient_id)
        if values.supersedes_id is not None:
            self._previous(self.weights, actor, patient_id, values.supersedes_id)
        weight = WeightRecord(
            clinic_id=self.weights.context.clinic_id,
            patient_id=patient_id,
            author_id=actor.id,
            author_name=actor.name,
            **values.model_dump(),
        )
        self._save(self.weights, weight)
        action = "create" if values.supersedes_id is None else "correct"
        self.audit.add(actor.id, action, "weight", weight.id, patient_id)
        return WeightRead.model_validate(weight, from_attributes=True)

    def add_vaccine(self, actor: User, patient_id: UUID, values: VaccineCreate) -> VaccineRead:
        crmv = require_clinician(actor)
        self.scheduling.patients.get(patient_id, include_archived=True)
        encounter = self.scheduling.get_encounter(values.encounter_id)
        if encounter.patient_id != patient_id:
            raise InvalidData("O atendimento informado é de outro paciente.")
        if values.expires_on < values.manufactured_on:
            raise InvalidData("A validade deve ser posterior à data de fabricação.")
        applied_on = datetime.now(TIMEZONE).date()
        if values.supersedes_id is not None:
            previous = self._previous(self.vaccines, actor, patient_id, values.supersedes_id)
            # A correção vale para a data em que a vacina foi aplicada, não para hoje.
            applied_on = previous.created_at.astimezone(TIMEZONE).date()
        if values.expires_on < applied_on:
            raise InvalidData("A vacina estava vencida na data de aplicação.")
        if values.next_dose_on is not None and values.next_dose_on <= applied_on:
            raise InvalidData("A revacinação deve ser posterior à data de aplicação.")
        vaccine = VaccineRecord(
            clinic_id=self.vaccines.context.clinic_id,
            patient_id=patient_id,
            author_id=actor.id,
            author_name=actor.name,
            author_crmv=crmv,
            **values.model_dump(),
        )
        self._save(self.vaccines, vaccine)
        action = "create" if values.supersedes_id is None else "correct"
        self.audit.add(actor.id, action, "vaccine", vaccine.id, patient_id)
        return VaccineRead.model_validate(vaccine, from_attributes=True)
