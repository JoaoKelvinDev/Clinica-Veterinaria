from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import AuthContext
from app.modules.tutors.repositories import TutorRepository
from app.modules.tutors.schemas import ConsentInput, TutorCreate, TutorPage, TutorRead, TutorUpdate
from app.modules.tutors.services import TutorService

router = APIRouter(prefix="/tutors", tags=["Tutores"])


def tutor_service(auth: AuthContext) -> TutorService:
    return TutorService(TutorRepository(auth.session, auth.clinic))


Service = Annotated[TutorService, Depends(tutor_service)]


@router.get("", response_model=TutorPage)
def list_tutors(
    service: Service,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TutorPage:
    return service.list(q, limit, offset)


@router.post("", response_model=TutorRead, status_code=201)
def create_tutor(values: TutorCreate, auth: AuthContext, service: Service) -> TutorRead:
    return TutorRead.model_validate(service.create(auth.actor, values))


@router.get("/{tutor_id}", response_model=TutorRead)
def get_tutor(tutor_id: UUID, service: Service) -> TutorRead:
    return TutorRead.model_validate(service.get(tutor_id))


@router.patch("/{tutor_id}", response_model=TutorRead)
def update_tutor(
    tutor_id: UUID, changes: TutorUpdate, auth: AuthContext, service: Service
) -> TutorRead:
    return TutorRead.model_validate(service.update(auth.actor, tutor_id, changes))


@router.put("/{tutor_id}/whatsapp-consent", response_model=TutorRead)
def set_consent(
    tutor_id: UUID, values: ConsentInput, auth: AuthContext, service: Service
) -> TutorRead:
    return TutorRead.model_validate(service.consent(auth.actor, tutor_id, values))


@router.delete("/{tutor_id}", status_code=204)
def archive_tutor(tutor_id: UUID, auth: AuthContext, service: Service) -> Response:
    service.archive(auth.actor, tutor_id)
    return Response(status_code=204)
