from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import Database, set_context, verify_runtime_role
from app.core.errors import AccessDenied, AuthenticationRequired, ServiceUnavailable
from app.core.repositories import ClinicContext
from app.modules.clinics.models import User
from app.modules.clinics.repositories import ClinicRepository, IdentityRepository
from app.modules.clinics.services import ClinicService
from app.providers.auth import AuthProvider

bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedContext:
    session: Session
    actor: User
    clinic: ClinicContext


def authenticated_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Iterator[AuthenticatedContext]:
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
            set_context(session, "vetsys.user_id", str(actor.id))
            clinic = ClinicContext(actor.clinic_id)
            ClinicService(ClinicRepository(session, clinic)).current()
            yield AuthenticatedContext(session, actor, clinic)
    except SQLAlchemyError:
        raise ServiceUnavailable("Não foi possível acessar os dados da clínica.") from None


AuthContext = Annotated[AuthenticatedContext, Depends(authenticated_context, scope="function")]
