from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext
from app.modules.records.schemas import (
    PatientRecord,
    RecordEntryCreate,
    RecordEntryRead,
    VaccineCreate,
    VaccineRead,
    WeightCreate,
    WeightRead,
)
from app.modules.records.services import RecordService

router = APIRouter(tags=["Prontuário"])


def record_service(auth: AuthContext) -> RecordService:
    return RecordService.for_clinic(auth.session, auth.clinic)


Service = Annotated[RecordService, Depends(record_service)]


@router.get("/patients/{patient_id}/record", response_model=PatientRecord)
def record(patient_id: UUID, auth: AuthContext, service: Service) -> PatientRecord:
    return service.record(auth.actor, patient_id)


@router.post(
    "/encounters/{encounter_id}/record-entries", response_model=RecordEntryRead, status_code=201
)
def add_entry(
    encounter_id: UUID, values: RecordEntryCreate, auth: AuthContext, service: Service
) -> RecordEntryRead:
    return service.add_entry(auth.actor, encounter_id, values)


@router.get("/record-entries/{entry_id}/versions", response_model=list[RecordEntryRead])
def versions(entry_id: UUID, auth: AuthContext, service: Service) -> list[RecordEntryRead]:
    return service.versions(auth.actor, entry_id)


@router.post("/patients/{patient_id}/weights", response_model=WeightRead, status_code=201)
def add_weight(
    patient_id: UUID, values: WeightCreate, auth: AuthContext, service: Service
) -> WeightRead:
    return service.add_weight(auth.actor, patient_id, values)


@router.post("/patients/{patient_id}/vaccines", response_model=VaccineRead, status_code=201)
def add_vaccine(
    patient_id: UUID, values: VaccineCreate, auth: AuthContext, service: Service
) -> VaccineRead:
    return service.add_vaccine(auth.actor, patient_id, values)
