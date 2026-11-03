from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AuthContext
from app.modules.scheduling.schemas import (
    AppointmentCreate,
    AppointmentPage,
    AppointmentRead,
    AppointmentUpdate,
    EncounterCreate,
    EncounterPage,
    EncounterRead,
    StatusInput,
)
from app.modules.scheduling.services import SchedulingService

router = APIRouter(tags=["Agenda e atendimentos"])


def scheduling_service(auth: AuthContext) -> SchedulingService:
    return SchedulingService.for_clinic(auth.session, auth.clinic)


Service = Annotated[SchedulingService, Depends(scheduling_service)]


@router.get("/appointments", response_model=AppointmentPage)
def appointments(
    service: Service,
    day: date,
    veterinarian_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AppointmentPage:
    return service.search(day, veterinarian_id, limit, offset)


@router.post("/appointments", response_model=AppointmentRead, status_code=201)
def create(values: AppointmentCreate, auth: AuthContext, service: Service) -> AppointmentRead:
    return service.appointment_read(service.create(auth.actor, values))


@router.get("/appointments/{appointment_id}", response_model=AppointmentRead)
def appointment(appointment_id: UUID, service: Service) -> AppointmentRead:
    return service.appointment_read(service.get(appointment_id))


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
def update(
    appointment_id: UUID, values: AppointmentUpdate, auth: AuthContext, service: Service
) -> AppointmentRead:
    return service.appointment_read(service.update(auth.actor, appointment_id, values))


@router.put("/appointments/{appointment_id}/status", response_model=AppointmentRead)
def status(
    appointment_id: UUID, values: StatusInput, auth: AuthContext, service: Service
) -> AppointmentRead:
    return service.appointment_read(
        service.change_status(auth.actor, appointment_id, values.status)
    )


@router.post("/appointments/{appointment_id}/start", response_model=EncounterRead)
def start(appointment_id: UUID, auth: AuthContext, service: Service) -> EncounterRead:
    return service.encounter_read(service.start(auth.actor, appointment_id))


@router.post("/encounters", response_model=EncounterRead, status_code=201)
def walk_in(values: EncounterCreate, auth: AuthContext, service: Service) -> EncounterRead:
    return service.encounter_read(service.start_walk_in(auth.actor, values.patient_id))


@router.get("/encounters", response_model=EncounterPage)
def encounters(
    service: Service,
    day: date,
    veterinarian_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EncounterPage:
    return service.search_encounters(day, veterinarian_id, limit, offset)


@router.get("/encounters/{encounter_id}", response_model=EncounterRead)
def encounter(encounter_id: UUID, service: Service) -> EncounterRead:
    return service.encounter_read(service.get_encounter(encounter_id))


@router.post("/encounters/{encounter_id}/complete", response_model=EncounterRead)
def complete(encounter_id: UUID, auth: AuthContext, service: Service) -> EncounterRead:
    return service.encounter_read(service.complete(auth.actor, encounter_id))
