from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.dependencies import AuthContext, ConsistentAuthContext
from app.modules.records.documents import StoredFile
from app.modules.records.export_schemas import ExportCreate, ExportOptions, ExportPage, ExportRead
from app.modules.records.exports import ExportService
from app.providers.storage import FileStorage

router = APIRouter(tags=["Exportação do prontuário"])


def export_service(request: Request, auth: AuthContext) -> ExportService:
    return ExportService.for_clinic(
        auth.session, auth.clinic, cast(FileStorage, request.app.state.file_storage)
    )


def consistent_export_service(request: Request, auth: ConsistentAuthContext) -> ExportService:
    return ExportService.for_clinic(
        auth.session, auth.clinic, cast(FileStorage, request.app.state.file_storage)
    )


Service = Annotated[ExportService, Depends(export_service)]
ConsistentService = Annotated[ExportService, Depends(consistent_export_service)]


@router.get("/patients/{patient_id}/record-exports/options", response_model=ExportOptions)
def options(patient_id: UUID, auth: AuthContext, service: Service) -> ExportOptions:
    return service.options(auth.actor, patient_id)


@router.get("/patients/{patient_id}/record-exports", response_model=ExportPage)
def list_exports(
    patient_id: UUID,
    auth: AuthContext,
    service: Service,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ExportPage:
    return service.list(auth.actor, patient_id, limit, offset)


@router.post("/patients/{patient_id}/record-exports", response_model=ExportRead, status_code=201)
def create(
    patient_id: UUID, values: ExportCreate, auth: ConsistentAuthContext, service: ConsistentService
) -> ExportRead:
    return service.create(auth.actor, patient_id, values)


def download(stored: StoredFile) -> Response:
    return Response(
        content=stored.content,
        media_type=stored.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(stored.file_name)}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.get("/record-exports/{export_id}/file")
def pdf_file(export_id: UUID, auth: AuthContext, service: Service) -> Response:
    return download(service.file(auth.actor, export_id))


@router.get("/record-exports/{export_id}/package")
def package(export_id: UUID, auth: AuthContext, service: Service) -> Response:
    return download(service.package(auth.actor, export_id))
