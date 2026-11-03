"""Laudos e documentos externos do paciente (art. 9º, X, da Resolução CFMV 1321/2020)."""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    AccessDenied,
    BusinessConflict,
    InvalidData,
    ResourceNotFound,
    ServiceUnavailable,
)
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.records.models import MAX_DOCUMENT_BYTES, PatientDocument
from app.modules.records.repositories import AuditRepository, DocumentRepository
from app.modules.records.schemas import DocumentCreate, DocumentRead
from app.modules.records.services import require_clinical_reader
from app.modules.scheduling.services import SchedulingService
from app.providers.storage import FileStorage

TIMEZONE = ZoneInfo("America/Fortaleza")
# Tipo identificado pelo conteúdo do arquivo; extensão e tipo declarado são ignorados.
SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


@dataclass(frozen=True)
class Upload:
    content: bytes
    file_name: str


@dataclass(frozen=True)
class StoredFile:
    content: bytes
    content_type: str
    file_name: str


def detect_type(content: bytes) -> str:
    for signature, content_type in SIGNATURES:
        if content.startswith(signature):
            return content_type
    raise InvalidData("Envie um arquivo PDF, JPG ou PNG.")


def safe_file_name(name: str) -> str:
    base = re.split(r"[\\/]", name)[-1]
    base = "".join(c for c in unicodedata.normalize("NFC", base) if c.isprintable())
    base = re.sub(r"[\"<>|:*?]", "_", base).strip(" .")
    return base[:200] or "documento"


def require_document_writer(actor: User) -> str | None:
    """Retorna o CRMV gravado com o documento, quando o autor é veterinário."""
    if (
        not actor.active
        or actor.deleted_at is not None
        or actor.role
        not in {
            Role.VETERINARIAN,
            Role.ASSISTANT,
        }
    ):
        raise AccessDenied("Somente veterinários e auxiliares adicionam documentos.")
    if actor.role == Role.VETERINARIAN and actor.crmv and actor.crmv_state:
        return f"CRMV-{actor.crmv_state} {actor.crmv}"
    return None


class DocumentService:
    @classmethod
    def for_clinic(
        cls, session: Session, context: ClinicContext, storage: FileStorage
    ) -> "DocumentService":
        return cls(
            DocumentRepository(session, context),
            AuditRepository(session, context),
            SchedulingService.for_clinic(session, context),
            storage,
        )

    def __init__(
        self,
        documents: DocumentRepository,
        audit: AuditRepository,
        scheduling: SchedulingService,
        storage: FileStorage,
    ) -> None:
        self.documents = documents
        self.audit = audit
        self.scheduling = scheduling
        self.storage = storage

    def add(
        self, actor: User, patient_id: UUID, values: DocumentCreate, upload: Upload | None
    ) -> DocumentRead:
        author_crmv = require_document_writer(actor)
        self.scheduling.patients.get(patient_id, include_archived=True)
        if values.encounter_id is not None:
            encounter = self.scheduling.get_encounter(values.encounter_id)
            if encounter.patient_id != patient_id:
                raise InvalidData("O atendimento informado é de outro paciente.")
        if values.document_date > datetime.now(TIMEZONE).date():
            raise InvalidData("A data do documento não pode estar no futuro.")
        document_id = uuid4()
        root_id, version = document_id, 1
        file_fields: dict[str, object] = {}
        if values.supersedes_id is not None:
            previous = self.documents.get(values.supersedes_id)
            if previous is None or previous.patient_id != patient_id:
                raise ResourceNotFound("Documento a corrigir não encontrado para este paciente.")
            if previous.author_id != actor.id:
                raise AccessDenied("Somente o autor pode corrigir o próprio documento.")
            if self.documents.is_superseded(previous.id):
                raise BusinessConflict(
                    "Este documento já foi corrigido. Corrija a versão mais recente."
                )
            root_id, version = previous.root_id, previous.version + 1
            if upload is None and values.keep_file and previous.file_key:
                file_fields = {
                    "file_key": previous.file_key,
                    "file_name": previous.file_name,
                    "content_type": previous.content_type,
                    "size_bytes": previous.size_bytes,
                    "sha256": previous.sha256,
                }
        elif values.keep_file:
            raise InvalidData("Só é possível manter o arquivo ao corrigir um documento.")
        if upload is not None:
            if not upload.content:
                raise InvalidData("O arquivo enviado está vazio.")
            if len(upload.content) > MAX_DOCUMENT_BYTES:
                raise InvalidData("O arquivo passa de 10 MB.")
            content_type = detect_type(upload.content)
            key = f"{self.documents.context.clinic_id}/{patient_id}/{document_id}"
            # O arquivo é guardado antes do registro: se o registro falhar, sobra só um
            # objeto sem referência, nunca um registro apontando para arquivo inexistente.
            self.storage.put(key, upload.content, content_type)
            file_fields = {
                "file_key": key,
                "file_name": safe_file_name(upload.file_name),
                "content_type": content_type,
                "size_bytes": len(upload.content),
                "sha256": hashlib.sha256(upload.content).hexdigest(),
            }
        if values.summary is None and not file_fields:
            raise InvalidData("Anexe um arquivo ou escreva um resumo do documento.")
        document = PatientDocument(
            id=document_id,
            clinic_id=self.documents.context.clinic_id,
            patient_id=patient_id,
            encounter_id=values.encounter_id,
            root_id=root_id,
            version=version,
            supersedes_id=values.supersedes_id,
            correction_reason=values.correction_reason,
            kind=values.kind,
            origin_name=values.origin_name,
            origin_crmv=values.origin_crmv,
            document_date=values.document_date,
            summary=values.summary,
            author_id=actor.id,
            author_name=actor.name,
            author_crmv=author_crmv,
            **file_fields,
        )
        try:
            self.documents.save(document)
        except IntegrityError:
            raise BusinessConflict(
                "Outro registro foi salvo ao mesmo tempo. Atualize o prontuário e tente de novo."
            ) from None
        action = "create" if version == 1 else "correct"
        self.audit.add(actor.id, action, "document", document.id, patient_id)
        return DocumentRead.model_validate(document, from_attributes=True)

    def versions(self, actor: User, document_id: UUID) -> list[DocumentRead]:
        require_clinical_reader(actor)
        document = self.documents.get(document_id)
        if document is None:
            raise ResourceNotFound("Documento não encontrado.")
        self.audit.add(actor.id, "read", "document", document.root_id, document.patient_id)
        return [
            DocumentRead.model_validate(item, from_attributes=True)
            for item in self.documents.versions(document.root_id)
        ]

    def file(self, actor: User, document_id: UUID) -> StoredFile:
        require_clinical_reader(actor)
        document = self.documents.get(document_id)
        if document is None or document.file_key is None:
            raise ResourceNotFound("Arquivo não encontrado.")
        content = self.storage.get(document.file_key)
        if hashlib.sha256(content).hexdigest() != document.sha256:
            raise ServiceUnavailable(
                "O arquivo guardado não confere com o registrado. Avise o administrador."
            )
        self.audit.add(actor.id, "read", "document_file", document.id, document.patient_id)
        assert document.content_type is not None and document.file_name is not None
        return StoredFile(content, document.content_type, document.file_name)
