import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from app.core.errors import DomainError, InvalidData, ResourceNotFound, ServiceUnavailable
from app.core.repositories import ClinicContext
from app.modules.clinics.models import User
from app.modules.patients.schemas import PatientRead
from app.modules.records.documents import DocumentService, StoredFile, safe_file_name
from app.modules.records.export_models import RecordExport
from app.modules.records.export_repository import ExportRepository
from app.modules.records.export_schemas import (
    Attachment,
    ExportCreate,
    ExportOptions,
    ExportPage,
    ExportRead,
    ExportSnapshot,
)
from app.modules.records.pdf import build_pdf
from app.modules.records.services import RecordService, require_clinical_reader, require_clinician
from app.modules.tutors.services import normalize_phone
from app.providers.storage import FileStorage

MAX_PACKAGE_BYTES = 100 * 1024 * 1024


def cpf_digits(value: str | None) -> str:
    digits = re.sub(r"[.\-\s]", "", value or "")
    if not re.fullmatch(r"[0-9]{11}", digits) or len(set(digits)) == 1:
        raise InvalidData("Corrija o CPF do responsável no cadastro antes de emitir o prontuário.")
    return digits


class ExportService:
    @classmethod
    def for_clinic(
        cls, session: Session, context: ClinicContext, storage: FileStorage
    ) -> "ExportService":
        return cls(
            ExportRepository(session, context),
            RecordService.for_clinic(session, context),
            DocumentService.for_clinic(session, context, storage),
            storage,
        )

    def __init__(
        self,
        exports: ExportRepository,
        records: RecordService,
        documents: DocumentService,
        storage: FileStorage,
    ) -> None:
        self.exports, self.records, self.documents, self.storage = (
            exports,
            records,
            documents,
            storage,
        )

    def options(self, actor: User, patient_id: UUID) -> ExportOptions:
        require_clinician(actor)
        patients = self.records.scheduling.patients
        patient = patients.get(patient_id, include_archived=True)
        return ExportOptions(
            clinic_name=self.records.clinics.current().name,
            patient_name=patient.name,
            tutors=patients.record_tutors(patient_id),
        )

    def list(self, actor: User, patient_id: UUID, limit: int, offset: int) -> ExportPage:
        require_clinical_reader(actor)
        self.records.scheduling.patients.get(patient_id, include_archived=True)
        items, total = self.exports.page(patient_id, limit, offset)
        self.records.audit.add(actor.id, "read", "record_export_list", patient_id, patient_id)
        return ExportPage(items=[ExportRead.model_validate(item) for item in items], total=total)

    def create(self, actor: User, patient_id: UUID, values: ExportCreate) -> ExportRead:
        author_crmv = require_clinician(actor)
        patients = self.records.scheduling.patients
        patient = patients.get(patient_id, include_archived=True)
        link = next(
            (
                link
                for link in patients.record_tutors(patient_id)
                if link.tutor.id == values.tutor_id
            ),
            None,
        )
        if link is None:
            raise InvalidData("Selecione um responsável vinculado ao paciente.")
        tutor = link.tutor
        cpf = cpf_digits(tutor.document)
        if tutor.address is None or not tutor.address.strip():
            raise InvalidData("Complete o endereço do responsável no cadastro antes de emitir.")
        phone = normalize_phone(values.professional_phone)
        if phone is None:
            raise InvalidData("Informe o telefone profissional.")
        emission = values.model_copy(update={"professional_phone": phone})
        if values.establishment_cnpj is not None:
            cnpj = re.sub(r"[.\-/\s]", "", values.establishment_cnpj)
            if not re.fullmatch(r"[0-9]{14}", cnpj):
                raise InvalidData("Informe um CNPJ com 14 dígitos.")
            emission = emission.model_copy(update={"establishment_cnpj": cnpj})
        record = self.records.export_record(actor, patient_id)
        export_id, generated_at = uuid4(), datetime.now(UTC)
        attachments = [
            Attachment(
                document_id=item.id,
                file_name=item.file_name,
                content_type=item.content_type,
                size_bytes=item.size_bytes,
                sha256=item.sha256,
            )
            for item in record.documents
            if item.file_name is not None
            and item.content_type is not None
            and item.size_bytes is not None
            and item.sha256 is not None
        ]
        if sum(item.size_bytes for item in attachments) > MAX_PACKAGE_BYTES:
            raise InvalidData("Os anexos excedem 100 MB. Nenhuma exportação foi registrada.")
        # Valida todos os originais antes de anunciar uma emissão pronta.
        for attachment in attachments:
            self._attachment(actor, attachment)
        snapshot = ExportSnapshot(
            export_id=export_id,
            generated_at=generated_at,
            clinic_name=self.records.clinics.current().name,
            patient=PatientRead.model_validate(patient),
            tutor=tutor.model_copy(update={"document": cpf}),
            author_name=actor.name,
            author_crmv=author_crmv,
            emission=emission,
            record=record,
        )
        try:
            content = build_pdf(snapshot)
        except DomainError:
            raise
        except Exception as error:
            # Exceções da biblioteca podem conter o parágrafo clínico: não logar traceback.
            logging.getLogger(__name__).error("PDF renderer failure: %s", type(error).__name__)
            raise ServiceUnavailable(
                "Não foi possível gerar o PDF. Nenhuma exportação foi registrada."
            ) from None
        if len(content) + sum(item.size_bytes for item in attachments) > MAX_PACKAGE_BYTES:
            raise InvalidData(
                "O PDF com os anexos excede 100 MB. Nenhuma exportação foi registrada."
            )
        key = f"{patient.clinic_id}/{patient_id}/exports/{export_id}.pdf"
        self.storage.put(key, content, "application/pdf")
        exported = RecordExport(
            id=export_id,
            clinic_id=patient.clinic_id,
            patient_id=patient_id,
            tutor_id=tutor.id,
            author_id=actor.id,
            author_name=actor.name,
            author_crmv=author_crmv,
            tutor_name=tutor.name,
            file_key=key,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            attachment_count=len(attachments),
            missing_file_count=len(record.documents) - len(attachments),
            attachments=[item.model_dump(mode="json") for item in attachments],
            created_at=generated_at,
            updated_at=generated_at,
        )
        # Como nos anexos, falha no banco pode deixar objeto órfão, sem emissão visível.
        self.exports.save(exported)
        self.records.audit.add(actor.id, "create", "record_export", export_id, patient_id)
        return ExportRead.model_validate(exported)

    def _get(self, actor: User, export_id: UUID) -> RecordExport:
        require_clinical_reader(actor)
        exported = self.exports.get(export_id)
        if exported is None:
            raise ResourceNotFound("Exportação não encontrada.")
        return exported

    def _pdf(self, exported: RecordExport) -> bytes:
        content = self.storage.get(exported.file_key)
        if (
            len(content) != exported.size_bytes
            or hashlib.sha256(content).hexdigest() != exported.sha256
        ):
            raise ServiceUnavailable(
                "O PDF guardado não confere com a emissão. Avise o administrador."
            )
        return content

    def _attachment(self, actor: User, attachment: Attachment) -> StoredFile:
        stored = self.documents.file(actor, attachment.document_id)
        if (
            len(stored.content) != attachment.size_bytes
            or hashlib.sha256(stored.content).hexdigest() != attachment.sha256
        ):
            raise ServiceUnavailable("Um anexo não confere com a emissão. Avise o administrador.")
        return stored

    def file(self, actor: User, export_id: UUID) -> StoredFile:
        exported = self._get(actor, export_id)
        content = self._pdf(exported)
        self.records.audit.add(
            actor.id, "read", "record_export_pdf", export_id, exported.patient_id
        )
        return StoredFile(content, "application/pdf", f"prontuario-{export_id}.pdf")

    def package(self, actor: User, export_id: UUID) -> StoredFile:
        exported = self._get(actor, export_id)
        pdf = self._pdf(exported)
        attachments = [Attachment.model_validate(item) for item in exported.attachments]
        if len(pdf) + sum(item.size_bytes for item in attachments) > MAX_PACKAGE_BYTES:
            raise InvalidData("O pacote excede 100 MB. Baixe o PDF e os anexos separadamente.")
        output = BytesIO()
        manifest: list[dict[str, object]] = []
        with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("prontuario.pdf", pdf)
            for attachment in attachments:
                stored = self._attachment(actor, attachment)
                path = f"anexos/{attachment.document_id}/{safe_file_name(attachment.file_name)}"
                archive.writestr(path, stored.content)
                manifest.append({**attachment.model_dump(mode="json"), "path": path})
            archive.writestr(
                "manifesto.json",
                json.dumps(
                    {
                        "export_id": str(export_id),
                        "pdf_sha256": exported.sha256,
                        "assinatura_digital_incorporada": False,
                        "download_comprova_recebimento": False,
                        "documentos_sem_arquivo": exported.missing_file_count,
                        "anexos": manifest,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        self.records.audit.add(
            actor.id, "read", "record_export_zip", export_id, exported.patient_id
        )
        return StoredFile(output.getvalue(), "application/zip", f"prontuario-{export_id}.zip")
