from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import AuthContext
from app.modules.patients.repositories import LinkRepository, PatientRepository
from app.modules.patients.schemas import (
    PatientCreate,
    PatientPage,
    PatientRead,
    PatientUpdate,
    TutorLinkInput,
    TutorLinkRead,
)
from app.modules.patients.services import PatientService
from app.modules.tutors.services import TutorService

router = APIRouter(prefix="/patients", tags=["Pacientes"])


def patient_service(auth: AuthContext) -> PatientService:
    return PatientService(
        PatientRepository(auth.session, auth.clinic),
        LinkRepository(auth.session, auth.clinic),
        TutorService.for_clinic(auth.session, auth.clinic),
    )


Service = Annotated[PatientService, Depends(patient_service)]


@router.get("", response_model=PatientPage)
def list_patients(
    service: Service,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> PatientPage:
    return service.search(q, limit, offset)


@router.post("", response_model=PatientRead, status_code=201)
def create_patient(values: PatientCreate, auth: AuthContext, service: Service) -> PatientRead:
    return PatientRead.model_validate(service.create(auth.actor, values))


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient_id: UUID, service: Service) -> PatientRead:
    return PatientRead.model_validate(service.get(patient_id))


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(
    patient_id: UUID, values: PatientUpdate, auth: AuthContext, service: Service
) -> PatientRead:
    return PatientRead.model_validate(service.update(auth.actor, patient_id, values))


@router.delete("/{patient_id}", status_code=204)
def archive_patient(patient_id: UUID, auth: AuthContext, service: Service) -> Response:
    service.archive(auth.actor, patient_id)
    return Response(status_code=204)


@router.get("/{patient_id}/tutors", response_model=list[TutorLinkRead])
def list_tutors(patient_id: UUID, service: Service) -> list[TutorLinkRead]:
    return service.list_tutors(patient_id)


@router.post("/{patient_id}/tutors", response_model=list[TutorLinkRead])
def link_tutor(
    patient_id: UUID, values: TutorLinkInput, auth: AuthContext, service: Service
) -> list[TutorLinkRead]:
    service.link(auth.actor, patient_id, values.tutor_id, values.is_primary)
    return service.list_tutors(patient_id)


@router.delete("/{patient_id}/tutors/{tutor_id}", status_code=204)
def unlink_tutor(patient_id: UUID, tutor_id: UUID, auth: AuthContext, service: Service) -> Response:
    service.unlink(auth.actor, patient_id, tutor_id)
    return Response(status_code=204)
