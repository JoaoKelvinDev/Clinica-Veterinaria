"""Entrada HTTP; regras de negócio permanecem nos services."""

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import DomainError
from app.modules.clinics.api import router
from app.modules.messaging.api import router as messaging_router
from app.modules.patients.api import router as patients_router
from app.modules.records.api import router as records_router
from app.modules.scheduling.api import router as scheduling_router
from app.modules.tutors.api import router as tutors_router
from app.providers.auth import AuthProvider, SupabaseAuthProvider
from app.providers.messaging import MessagingProvider, MockMessagingProvider
from app.providers.storage import FileStorage, SupabaseFileStorage


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    auth_provider: AuthProvider | None = None,
    file_storage: FileStorage | None = None,
    messaging_provider: MessagingProvider | None = None,
) -> FastAPI:
    config = settings or Settings.from_environment()
    application = FastAPI(title="Sistema Veterinário", version="0.7.0")
    application.state.database = database or (
        Database(config.database_url) if config.database_url else None
    )
    application.state.auth_provider = auth_provider or SupabaseAuthProvider(
        config.supabase_url, config.supabase_key
    )
    application.state.file_storage = file_storage or SupabaseFileStorage(
        config.supabase_url, config.supabase_secret_key
    )
    # Etapa 5: somente envio simulado (MOCK), sem custo e sem WhatsApp real.
    application.state.messaging_provider = messaging_provider or MockMessagingProvider()

    @application.exception_handler(DomainError)
    async def domain_error(_request: Request, error: DomainError) -> JSONResponse:
        statuses = {
            "unauthenticated": 401,
            "forbidden": 403,
            "not_found": 404,
            "conflict": 409,
            "invalid_data": 422,
            "unavailable": 503,
        }
        headers = {"WWW-Authenticate": "Bearer"} if error.code == "unauthenticated" else None
        return JSONResponse(
            status_code=statuses.get(error.code, 400),
            content={"error": {"code": error.code, "message": str(error)}},
            headers=headers,
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # Não devolve o payload recebido: ele pode conter dados pessoais ou credenciais.
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "invalid_data", "message": "Verifique os dados informados."}
            },
        )

    @application.get("/health", response_model=HealthResponse, tags=["Saúde"])
    def health() -> HealthResponse:
        """Verifica somente a disponibilidade da API, sem verificar banco de dados."""
        return HealthResponse()

    application.include_router(router)
    application.include_router(tutors_router)
    application.include_router(patients_router)
    application.include_router(scheduling_router)
    application.include_router(records_router)
    application.include_router(messaging_router)
    return application


app = create_app()
