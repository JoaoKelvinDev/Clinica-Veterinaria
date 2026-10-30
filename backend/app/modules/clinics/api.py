from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import Database, set_context, verify_runtime_role
from app.core.errors import AccessDenied, AuthenticationRequired, ServiceUnavailable
from app.modules.clinics.models import User
from app.modules.clinics.repositories import (
    ClinicContext,
    ClinicRepository,
    IdentityRepository,
    UserRepository,
)
from app.modules.clinics.schemas import (
    ClinicRead,
    ClinicUpdate,
    IdentityRead,
    UserRead,
    UserUpdate,
)
from app.modules.clinics.services import ClinicService, UserService
from app.providers.auth import AuthProvider

router = APIRouter(tags=["Clínica e usuários"])
bearer = HTTPBearer(auto_error=False)


@dataclass
class RequestContext:
    actor: User
    clinics: ClinicService
    users: UserService


def request_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Iterator[RequestContext]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationRequired("Entre para acessar o sistema.")
    provider = cast(AuthProvider, request.app.state.auth_provider)
    auth_id = provider.verify(credentials.credentials)
    database = cast(Database | None, request.app.state.database)
    if database is None:
        raise ServiceUnavailable("O banco de dados ainda não está configurado.")
    try:
        with database.sessions.begin() as session:
            verify_runtime_role(session)
            set_context(session, "vetsys.auth_id", str(auth_id))
            actor = IdentityRepository(session).get_by_auth_id(auth_id)
            if actor is None or not actor.active or actor.deleted_at is not None:
                raise AccessDenied("Usuário sem acesso ativo a uma clínica.")
            set_context(session, "vetsys.clinic_id", str(actor.clinic_id))
            set_context(session, "vetsys.role", actor.role.value)
            context = ClinicContext(actor.clinic_id)
            clinics = ClinicRepository(session, context)
            clinic_service = ClinicService(clinics)
            clinic_service.current()
            yield RequestContext(
                actor, clinic_service, UserService(UserRepository(session, context), clinics)
            )
    except SQLAlchemyError:
        raise ServiceUnavailable("Não foi possível acessar os dados da clínica.") from None


Context = Annotated[RequestContext, Depends(request_context, scope="function")]


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
