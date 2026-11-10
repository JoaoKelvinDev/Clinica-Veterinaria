import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Event
from typing import Any
from unittest.mock import Mock
from uuid import UUID
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.errors import AccessDenied, ServiceUnavailable
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.records import exports
from app.modules.records.export_models import RecordExport
from app.modules.records.export_repository import ExportRepository
from app.modules.records.export_schemas import ExportCreate
from app.modules.records.exports import ExportService
from app.modules.records.models import AuditLog
from app.modules.records.services import RecordService
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_ai_scribe import generate
from tests.test_documents import PDF, send, storage
from tests.test_records import encounter, entry, vaccine
from tests.test_registry_api import headers, tutor

EMISSION = {
    "professional_address": "Rua Fictícia, 100, Centro, Teresina - PI",
    "professional_phone": "(86) 99999-1234",
    "professional_email": "vet@example.test",
    "establishment_legal_name": "Estabelecimento fictício",
    "establishment_cnpj": "12.345.678/0001-90",
    "establishment_crmv": "CRMV-PI PJ 123",
    "acknowledge_unsigned": True,
}


def setup_record(client: TestClient) -> tuple[dict[str, Any], dict[str, Any]]:
    opened = dict(encounter(client))
    responsible = tutor(
        client, document="123.456.789-09", address="Rua Fictícia, 10, Teresina - PI"
    )
    response = client.post(
        f"/patients/{opened['patient_id']}/tutors",
        headers=headers(),
        json={"tutor_id": responsible["id"]},
    )
    assert response.status_code == 200
    return opened, responsible


def emit(
    client: TestClient, opened: dict[str, Any], responsible: dict[str, Any], **changes: object
) -> dict[str, Any]:
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"], **changes},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def pdf(client: TestClient, exported: dict[str, Any], token: str = "vet_a") -> bytes:
    response = client.get(f"/record-exports/{exported['id']}/file", headers=headers(token))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    return bytes(response.content)


def text_of(content: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(content)).pages)


def test_pdf_content_versions_metadata_and_audit(
    client: TestClient, database: DatabaseFixture
) -> None:
    opened, responsible = setup_record(client)
    first = entry(client, opened["id"], complaint="Queixa anterior fictícia")
    entry(
        client,
        opened["id"],
        complaint="Relato corrigido: cão com náusea <tag> & aspas",
        supersedes_id=first["id"],
        correction_reason="Correção da queixa inicial",
    )
    assert (
        client.post(
            f"/patients/{opened['patient_id']}/weights",
            headers=headers("assistant_a"),
            json={"weight_grams": 12500},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/patients/{opened['patient_id']}/vaccines",
            headers=headers("vet_a"),
            json=vaccine(encounter_id=opened["id"]),
        ).status_code
        == 201
    )
    assert send(client, opened["patient_id"]).status_code == 201  # type: ignore[attr-defined]
    exported = emit(client, opened, responsible)
    content = pdf(client, exported)
    extracted = text_of(content)
    for expected in (
        "Prontuário médico-veterinário",
        "SEM ASSINATURA DIGITAL INCORPORADA",
        "12345678909",
        "CRMV-PI 1234",
        "Relato corrigido: cão com náusea <tag> & aspas",
        "Queixa anterior fictícia",
        "VERSÃO SUBSTITUÍDA",
        "Correção da queixa inicial",
        "12,5",
        "LOTE-FICTICIO",
        "Laboratório fictício",
        "Página 1 de",
    ):
        assert expected in extracted, expected
    assert extracted.index("Relato corrigido") < extracted.index("Queixa anterior")
    assert hashlib.sha256(content).hexdigest() == exported["sha256"]
    assert exported["attachment_count"] == 1
    assert "file_key" not in exported and "attachments" not in exported
    with Session(database.admin) as session:
        rows = session.scalars(
            select(AuditLog).where(AuditLog.entity_id == UUID(exported["id"]))
        ).all()
        assert {(row.action, row.entity) for row in rows} == {
            ("create", "record_export"),
            ("read", "record_export_pdf"),
        }


def test_old_export_keeps_exact_bytes_after_corrections(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    first = entry(client, opened["id"], complaint="Relato original")
    exported = emit(client, opened, responsible)
    original = pdf(client, exported)
    entry(
        client,
        opened["id"],
        supersedes_id=first["id"],
        correction_reason="Nova informação",
        complaint="Relato posterior",
    )
    assert (
        client.patch(
            f"/tutors/{responsible['id']}", headers=headers(), json={"name": "Novo nome fictício"}
        ).status_code
        == 200
    )
    assert pdf(client, exported) == original
    newer = emit(client, opened, responsible)
    assert newer["id"] != exported["id"] and "Relato posterior" in text_of(pdf(client, newer))
    assert "Novo nome fictício" not in text_of(original)


def test_zip_originals_manifest_and_missing_files(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    response = send(client, opened["patient_id"], file=("../laudo.pdf", PDF, "application/pdf"))
    assert response.status_code == 201  # type: ignore[attr-defined]
    assert (
        send(
            client, opened["patient_id"], file=None, summary="Resumo sem laudo original"
        ).status_code  # type: ignore[attr-defined]
        == 201
    )
    exported = emit(client, opened, responsible)
    package = client.get(
        f"/record-exports/{exported['id']}/package", headers=headers("assistant_a")
    )
    assert package.status_code == 200 and package.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(package.content)) as archive:
        manifest = json.loads(archive.read("manifesto.json"))
        assert archive.read(manifest["anexos"][0]["path"]) == PDF
        assert archive.read("prontuario.pdf") == pdf(client, exported)
        assert all(".." not in name.split("/") for name in archive.namelist())
        assert manifest["documentos_sem_arquivo"] == exported["missing_file_count"] == 1
        assert manifest["assinatura_digital_incorporada"] is False
        assert manifest["download_comprova_recebimento"] is False


@pytest.mark.parametrize(
    "token", ["admin_a", "assistant_a", "reception_a", "inactive_a", "deleted_a"]
)
def test_only_active_vet_creates(client: TestClient, token: str) -> None:
    opened, responsible = setup_record(client)
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers(token),
        json={**EMISSION, "tutor_id": responsible["id"]},
    )
    assert response.status_code == 403


def test_permissions_pagination_and_archived_patient(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    options = client.get(
        f"/patients/{opened['patient_id']}/record-exports/options", headers=headers("vet_a")
    )
    assert (
        options.status_code == 200
        and options.json()["tutors"][0]["tutor"]["id"] == responsible["id"]
    )
    exported = emit(client, opened, responsible)
    for token in ("admin_a", "vet_a", "assistant_a"):
        assert pdf(client, exported, token).startswith(b"%PDF-")
    for suffix in ("file", "package"):
        assert (
            client.get(
                f"/record-exports/{exported['id']}/{suffix}", headers=headers("reception_a")
            ).status_code
            == 403
        )
        assert client.get(f"/record-exports/{exported['id']}/{suffix}").status_code == 401
    assert (
        client.get(
            f"/patients/{opened['patient_id']}/record-exports", headers=headers("reception_a")
        ).status_code
        == 403
    )
    assert client.delete(f"/patients/{opened['patient_id']}", headers=headers()).status_code == 204
    assert pdf(client, exported).startswith(b"%PDF-")
    emit(client, opened, responsible)
    page = client.get(
        f"/patients/{opened['patient_id']}/record-exports?limit=1&offset=1", headers=headers()
    ).json()
    assert len(page["items"]) == 1 and page["total"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {"acknowledge_unsigned": False},
        {"acknowledge_unsigned": 1},
        {"professional_email": "inválido"},
        {"professional_phone": "00000000"},
        {"establishment_crmv": None},
        {"establishment_cnpj": "xxxxxxxxxxxxxx"},
        {"unexpected": "x"},
    ],
)
def test_input_validation(client: TestClient, changes: dict[str, object]) -> None:
    opened, responsible = setup_record(client)
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"], **changes},
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "changes", [{"document": None}, {"document": "documento-qualquer"}, {"address": None}]
)
def test_incomplete_tutor_blocks_export(client: TestClient, changes: dict[str, object]) -> None:
    opened, responsible = setup_record(client)
    assert (
        client.patch(f"/tutors/{responsible['id']}", headers=headers(), json=changes).status_code
        == 200
    )
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"]},
    )
    assert response.status_code == 422


def test_link_and_tenant_isolation(
    client: TestClient, database: DatabaseFixture, data: FixtureData
) -> None:
    opened, responsible = setup_record(client)
    other_tutor = tutor(client)
    assert (
        client.post(
            f"/patients/{opened['patient_id']}/record-exports",
            headers=headers("vet_a"),
            json={**EMISSION, "tutor_id": other_tutor["id"]},
        ).status_code
        == 422
    )
    exported = emit(client, opened, responsible)
    for suffix in ("file", "package"):
        assert (
            client.get(
                f"/record-exports/{exported['id']}/{suffix}", headers=headers("admin_b")
            ).status_code
            == 404
        )
    assert (
        client.get(
            f"/patients/{opened['patient_id']}/record-exports", headers=headers("admin_b")
        ).status_code
        == 404
    )
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_b.id))
        set_context(session, "vetsys.role", "admin")
        assert list(session.scalars(select(RecordExport))) == []
        assert (
            ExportRepository(session, ClinicContext(data.clinic_a.id)).get(UUID(exported["id"]))
            is None
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE vetsys.record_exports SET tutor_name = 'Alterado'",
        "DELETE FROM vetsys.record_exports",
    ],
)
def test_immutable_for_database_admin(
    client: TestClient, database: DatabaseFixture, statement: str
) -> None:
    opened, responsible = setup_record(client)
    exported = emit(client, opened, responsible)
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        connection.execute(text(statement))
    assert pdf(client, exported).startswith(b"%PDF-")


def test_storage_failure_no_export(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    opened, responsible = setup_record(client)

    def fail(*args: object) -> None:
        raise ServiceUnavailable("Falha simulada de armazenamento")

    monkeypatch.setattr(storage(client), "put", fail)
    result = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"]},
    )
    assert result.status_code == 503
    assert (
        client.get(f"/patients/{opened['patient_id']}/record-exports", headers=headers()).json()[
            "total"
        ]
        == 0
    )


def test_corrupt_original_or_pdf_blocks_download(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    send(client, opened["patient_id"])
    saved = storage(client)
    key = next(iter(saved.objects))
    original = saved.objects[key]
    saved.objects[key] = (b"corrompido", "application/pdf")
    assert (
        client.post(
            f"/patients/{opened['patient_id']}/record-exports",
            headers=headers("vet_a"),
            json={**EMISSION, "tutor_id": responsible["id"]},
        ).status_code
        == 503
    )
    saved.objects[key] = original
    exported = emit(client, opened, responsible)
    saved.objects[key] = (b"corrompido", "application/pdf")
    assert (
        client.get(f"/record-exports/{exported['id']}/package", headers=headers()).status_code
        == 503
    )
    pdf_key = next(name for name in saved.objects if "/exports/" in name)
    saved.objects[pdf_key] = (b"corrompido", "application/pdf")
    assert (
        client.get(f"/record-exports/{exported['id']}/file", headers=headers()).status_code == 503
    )


def test_long_text_markup_and_unicode(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    complaint = (
        "Início cão ação <b>literal</b> & fim 🐶\n"
        + ("Texto longo fictício. " * 800)
        + "MARCADOR-FINAL"
    )
    entry(client, opened["id"], complaint=complaint)
    exported = emit(client, opened, responsible)
    content = pdf(client, exported)
    reader, extracted = PdfReader(BytesIO(content)), text_of(content)
    assert len(reader.pages) > 5
    assert (
        "<b>literal</b>" in extracted and "[U+1F436]" in extracted and "MARCADOR-FINAL" in extracted
    )
    assert all(f"de {len(reader.pages)}" in page.extract_text() for page in reader.pages)


def test_snapshot_during_concurrent_correction(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, database: DatabaseFixture
) -> None:
    opened, responsible = setup_record(client)
    original = entry(client, opened["id"], complaint="ANTES DA EXPORTAÇÃO")
    reached, changed = Event(), Event()
    collect = RecordService.export_record

    def wait_for_change(self: RecordService, actor: Any, patient_id: UUID) -> Any:
        reached.set()
        assert changed.wait(timeout=15)
        assert self.entries.session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
        return collect(self, actor, patient_id)

    monkeypatch.setattr(RecordService, "export_record", wait_for_change)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(emit, client, opened, responsible)
        assert reached.wait(timeout=15)
        try:
            entry(
                client,
                opened["id"],
                complaint="DEPOIS DA EXPORTAÇÃO",
                supersedes_id=original["id"],
                correction_reason="Mudança concorrente fictícia",
            )
        finally:
            changed.set()
        exported = future.result(timeout=25)
    extracted = text_of(pdf(client, exported))
    assert "ANTES DA EXPORTAÇÃO" in extracted and "DEPOIS DA EXPORTAÇÃO" not in extracted
    with database.runtime.sessions.begin() as session:
        assert session.scalar(text("SHOW transaction_isolation")) == "read committed"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ASSISTANT, Role.RECEPTION])
def test_permission_before_data_or_storage_access(role: Role) -> None:
    repository, records, documents, storage_mock = Mock(), Mock(), Mock(), Mock()
    service = ExportService(repository, records, documents, storage_mock)
    from uuid import uuid4

    values = ExportCreate.model_validate({**EMISSION, "tutor_id": uuid4()})
    with pytest.raises(AccessDenied):
        service.create(User(role=role, active=True, deleted_at=None), uuid4(), values)
    assert (
        repository.mock_calls
        == records.mock_calls
        == documents.mock_calls
        == storage_mock.mock_calls
        == []
    )


def test_pending_ai_text_is_never_in_pdf(client: TestClient) -> None:
    opened, responsible = setup_record(client)
    generate(
        client,
        opened["id"],
        source="text",
        transcript="Relato do responsável: RASCUNHO-NAO-APROVADO-PRIVADO",
    )
    exported = emit(client, opened, responsible)
    assert "RASCUNHO-NAO-APROVADO-PRIVADO" not in text_of(pdf(client, exported))


def test_render_failure_no_clinical_content_in_logs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    opened, responsible = setup_record(client)

    def fail(snapshot: object) -> bytes:
        raise ValueError("CONTEUDO-CLINICO-PRIVADO")

    monkeypatch.setattr(exports, "build_pdf", fail)
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"]},
    )
    assert response.status_code == 503
    assert "CONTEUDO-CLINICO-PRIVADO" not in response.text + caplog.text
    assert storage(client).objects == {}


def test_package_size_limit_does_not_record_partial_export(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened, responsible = setup_record(client)
    monkeypatch.setattr(exports, "MAX_PACKAGE_BYTES", 1)
    response = client.post(
        f"/patients/{opened['patient_id']}/record-exports",
        headers=headers("vet_a"),
        json={**EMISSION, "tutor_id": responsible["id"]},
    )
    assert response.status_code == 422
    assert storage(client).objects == {}
    assert (
        client.get(f"/patients/{opened['patient_id']}/record-exports", headers=headers()).json()[
            "total"
        ]
        == 0
    )
