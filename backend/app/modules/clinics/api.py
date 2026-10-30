from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import AuthContext
from app.modules.clinics.models import User
from app.modules.clinics.repositories import ClinicRepository, UserRepository
from app.modules.clinics.schemas import (
    ClinicRead,
    ClinicUpdate,
    IdentityRead,
    UserRead,
    UserUpdate,
)
from app.modules.clinics.services import ClinicService, UserService

router = APIRouter(tags=["Clínica e usuários"])


@dataclass
class RequestContext:
    actor: User
    clinics: ClinicService
    users: UserService


def clinic_services(auth: AuthContext) -> RequestContext:
    clinics = ClinicRepository(auth.session, auth.clinic)
    return RequestContext(
        auth.actor,
        ClinicService(clinics),
        UserService(UserRepository(auth.session, auth.clinic), clinics),
    )


Context = Annotated[RequestContext, Depends(clinic_services)]


@router.get("/me", response_model=IdentityRead)
def me(context: Context) -> IdentityRead:
    return IdentityRead(
        user=UserRead.model_validate(context.actor),
        clinic=ClinicRead.model_validate(context.clinics.current()),
    )


@router.get("/clinic", response_model=ClinicRead)
def clinic(context: Context) -> ClinicRead:
    return ClinicRead.model_validate(context.clinics.current())


@router.patch("/clinic", response_model=ClinicRead)
def update_clinic(changes: ClinicUpdate, context: Context) -> ClinicRead:
    return ClinicRead.model_validate(context.clinics.rename(context.actor, changes.name))


@router.get("/users", response_model=list[UserRead])
def users(context: Context) -> list[UserRead]:
    return [UserRead.model_validate(user) for user in context.users.list(context.actor)]


@router.get("/users/{user_id}", response_model=UserRead)
def user(user_id: UUID, context: Context) -> UserRead:
    return UserRead.model_validate(context.users.get(context.actor, user_id))


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(user_id: UUID, changes: UserUpdate, context: Context) -> UserRead:
    return UserRead.model_validate(context.users.update(context.actor, user_id, changes))
