from datetime import date
from typing import Annotated, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from pydantic import ValidationError

from app.core.dependencies import AuthContext
from app.core.errors import InvalidData
from app.modules.records.documents import DocumentService, Upload
from app.modules.records.models import MAX_DOCUMENT_BYTES
from app.modules.records.schemas import (
    DocumentCreate,
    DocumentRead,
    PatientRecord,
    RecordEntryCreate,
    RecordEntryRead,
    VaccineCreate,
    VaccineRead,
    WeightCreate,
    WeightRead,
)
from app.modules.records.services import RecordService
from app.providers.storage import FileStorage

router = APIRouter(tags=["Prontuário"])


def record_service(auth: AuthContext) -> RecordService:
    return RecordService.for_clinic(auth.session, auth.clinic)


Service = Annotated[RecordService, Depends(record_service)]


def document_service(request: Request, auth: AuthContext) -> DocumentService:
    return DocumentService.for_clinic(
        auth.session, auth.clinic, cast(FileStorage, request.app.state.file_storage)
    )


Documents = Annotated[DocumentService, Depends(document_service)]


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


@router.post("/patients/{patient_id}/documents", response_model=DocumentRead, status_code=201)
def add_document(
    request: Request,
    patient_id: UUID,
    auth: AuthContext,
    service: Documents,
    kind: Annotated[str, Form()],
    origin_name: Annotated[str, Form()],
    document_date: Annotated[date, Form()],
    origin_crmv: Annotated[str | None, Form()] = None,
    summary: Annotated[str | None, Form()] = None,
    encounter_id: Annotated[UUID | None, Form()] = None,
    supersedes_id: Annotated[UUID | None, Form()] = None,
    correction_reason: Annotated[str | None, Form()] = None,
    keep_file: Annotated[bool, Form()] = False,
    file: Annotated[UploadFile | None, File()] = None,
) -> DocumentRead:
    # Recusa cedo envios muito grandes, antes de processar o corpo inteiro.
    if int(request.headers.get("content-length") or 0) > MAX_DOCUMENT_BYTES + 1024 * 1024:
        raise InvalidData("O arquivo passa de 10 MB.")
    try:
        values = DocumentCreate(
            kind=kind,  # type: ignore[arg-type]
            origin_name=origin_name,
            origin_crmv=origin_crmv or None,
            document_date=document_date,
            summary=summary or None,
            encounter_id=encounter_id,
            supersedes_id=supersedes_id,
            correction_reason=correction_reason or None,
            keep_file=keep_file,
        )
    except ValidationError:
        raise InvalidData("Verifique os dados informados.") from None
    upload = None
    if file is not None and file.filename:
        upload = Upload(file.file.read(MAX_DOCUMENT_BYTES + 1), file.filename)
    return service.add(auth.actor, patient_id, values, upload)


@router.get("/documents/{document_id}/versions", response_model=list[DocumentRead])
def document_versions(
    document_id: UUID, auth: AuthContext, service: Documents
) -> list[DocumentRead]:
    return service.versions(auth.actor, document_id)


@router.get("/documents/{document_id}/file")
def document_file(document_id: UUID, auth: AuthContext, service: Documents) -> Response:
    stored = service.file(auth.actor, document_id)
    return Response(
        content=stored.content,
        media_type=stored.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(stored.file_name)}",
            "X-Content-Type-Options": "nosniff",
            # Um PDF ou imagem malicioso não executa nada no contexto do sistema.
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "no-store",
        },
    )
