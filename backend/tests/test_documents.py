from datetime import date, timedelta
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.errors import BusinessConflict
from app.modules.records.documents import safe_file_name
from app.modules.records.models import AuditLog, PatientDocument
from app.providers.storage import BUCKET, MemoryFileStorage, SupabaseFileStorage
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_records import encounter
from tests.test_registry_api import headers, patient

PDF = b"%PDF-1.7\n% laudo ficticio\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
FIELDS = {
    "kind": "lab_report",
    "origin_name": "Laboratório fictício",
    "document_date": str(date.today() - timedelta(days=3)),
}


def send(
    client: TestClient,
    patient_id: object,
    token: str = "vet_a",
    file: tuple[str, bytes, str] | None = ("laudo.pdf", PDF, "application/pdf"),
    **values: object,
) -> object:
    return client.post(
        f"/patients/{patient_id}/documents",
        headers=headers(token),
        data={**FIELDS, **{k: str(v) for k, v in values.items()}},
        files={"file": file} if file else None,
    )


def storage(client: TestClient) -> MemoryFileStorage:
    result = client.app.state.file_storage  # type: ignore[attr-defined]
    assert isinstance(result, MemoryFileStorage)
    return result


def test_file_summary_or_both_and_download_matches(client: TestClient) -> None:
    p = patient(client)
    only_file = send(client, p["id"])
    assert only_file.status_code == 201, only_file.text  # type: ignore[attr-defined]
    body = only_file.json()  # type: ignore[attr-defined]
    assert (body["content_type"], body["size_bytes"], body["file_name"]) == (
        "application/pdf",
        len(PDF),
        "laudo.pdf",
    )
    assert body["author_crmv"] == "CRMV-PI 1234"
    only_text = send(client, p["id"], file=None, summary="Hemograma sem alterações (fictício)")
    assert only_text.status_code == 201  # type: ignore[attr-defined]
    assert only_text.json()["file_name"] is None  # type: ignore[attr-defined]
    both = send(
        client,
        p["id"],
        token="assistant_a",
        file=("foto.png", PNG, "image/png"),
        kind="external_history",
        summary="Histórico de outra clínica (fictício)",
        origin_crmv="CRMV-CE 9999",
    )
    assert both.status_code == 201  # type: ignore[attr-defined]
    assert both.json()["author_crmv"] is None  # type: ignore[attr-defined]
    downloaded = client.get(f"/documents/{body['id']}/file", headers=headers("admin_a"))
    assert downloaded.status_code == 200
    assert downloaded.content == PDF
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in downloaded.headers["content-security-policy"]
    assert downloaded.headers["content-disposition"].startswith("attachment")
    record = client.get(f"/patients/{p['id']}/record", headers=headers()).json()
    assert len(record["documents"]) == 3


@pytest.mark.parametrize(
    "file,values",
    [
        (None, {}),
        (("virus.pdf", b"MZ\x90\x00 executavel", "application/pdf"), {}),
        (("vazio.pdf", b"", "application/pdf"), {"summary": "x"}),
        (("grande.pdf", PDF + b"0" * (10 * 1024 * 1024), "application/pdf"), {}),
        (("laudo.pdf", PDF, "application/pdf"), {"kind": "desconhecido"}),
        (("laudo.pdf", PDF, "application/pdf"), {"document_date": "2999-01-01"}),
        (("laudo.pdf", PDF, "application/pdf"), {"keep_file": "true"}),
    ],
)
def test_invalid_documents_are_rejected(
    client: TestClient,
    file: tuple[str, bytes, str] | None,
    values: dict[str, object],
) -> None:
    p = patient(client)
    response = send(client, p["id"], "vet_a", file, **values)
    assert response.status_code == 422, response.text  # type: ignore[attr-defined]


def test_correction_keeps_or_replaces_file_and_preserves_history(client: TestClient) -> None:
    p = patient(client)
    first = send(client, p["id"]).json()  # type: ignore[attr-defined]
    kept = send(
        client,
        p["id"],
        file=None,
        summary="Resumo acrescentado",
        supersedes_id=first["id"],
        correction_reason="Faltou o resumo",
        keep_file="true",
    )
    assert kept.status_code == 201, kept.text  # type: ignore[attr-defined]
    kept_body = kept.json()  # type: ignore[attr-defined]
    assert (kept_body["version"], kept_body["sha256"]) == (2, first["sha256"])
    again = send(
        client, p["id"], supersedes_id=first["id"], correction_reason="Segunda correção da v1"
    )
    assert again.status_code == 409  # type: ignore[attr-defined]
    other_author = send(
        client,
        p["id"],
        token="assistant_a",
        supersedes_id=kept_body["id"],
        correction_reason="Não sou o autor",
    )
    assert other_author.status_code == 403  # type: ignore[attr-defined]
    replaced = send(
        client,
        p["id"],
        file=("novo.png", PNG, "image/png"),
        supersedes_id=kept_body["id"],
        correction_reason="Arquivo errado",
    )
    assert replaced.status_code == 201  # type: ignore[attr-defined]
    versions = client.get(f"/documents/{first['id']}/versions", headers=headers()).json()
    types = [v["content_type"] for v in versions]
    assert types == ["application/pdf", "application/pdf", "image/png"]
    record = client.get(f"/patients/{p['id']}/record", headers=headers()).json()
    assert [d["version"] for d in record["documents"]] == [3]
    # A versão anterior continua com o arquivo original disponível.
    assert client.get(f"/documents/{first['id']}/file", headers=headers()).content == PDF


def test_encounter_link_must_match_patient(client: TestClient) -> None:
    opened = encounter(client)
    linked = send(client, opened["patient_id"], encounter_id=opened["id"])
    assert linked.status_code == 201  # type: ignore[attr-defined]
    other = patient(client)
    response = send(client, other["id"], encounter_id=opened["id"])
    assert response.status_code == 422  # type: ignore[attr-defined]


@pytest.mark.parametrize("token", ["admin_a", "reception_a"])
def test_only_clinical_team_adds_documents(client: TestClient, token: str) -> None:
    p = patient(client)
    assert send(client, p["id"], token=token).status_code == 403  # type: ignore[attr-defined]


def test_reception_and_other_clinic_cannot_open(client: TestClient) -> None:
    p = patient(client)
    created = send(client, p["id"]).json()  # type: ignore[attr-defined]
    url = f"/documents/{created['id']}"
    assert client.get(f"{url}/file", headers=headers("reception_a")).status_code == 403
    assert client.get(f"{url}/versions", headers=headers("reception_a")).status_code == 403
    assert client.get(f"{url}/file", headers=headers("admin_b")).status_code == 404
    assert client.get(f"/patients/{p['id']}/documents", headers=headers("admin_b")).status_code in {
        404,
        405,
    }
    assert send(client, p["id"], token="admin_b").status_code == 403  # type: ignore[attr-defined]
    record = client.get(f"/patients/{p['id']}/record", headers=headers("reception_a")).json()
    assert record["documents"] == []


def test_tampered_file_is_not_served(client: TestClient) -> None:
    p = patient(client)
    created = send(client, p["id"]).json()  # type: ignore[attr-defined]
    objects = storage(client).objects
    key = next(iter(objects))
    objects[key] = (PDF + b"alterado", "application/pdf")
    response = client.get(f"/documents/{created['id']}/file", headers=headers())
    assert response.status_code == 503


def test_audit_and_database_append_only(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    p = patient(client)
    created = send(client, p["id"]).json()  # type: ignore[attr-defined]
    client.get(f"/documents/{created['id']}/file", headers=headers())
    with Session(database.admin) as session:
        actions = session.execute(select(AuditLog.action, AuditLog.entity)).all()
        assert ("create", "document") in actions
        assert ("read", "document_file") in actions
    for statement in (
        "UPDATE vetsys.patient_documents SET summary = 'alterado' WHERE id = :id",
        "DELETE FROM vetsys.patient_documents WHERE id = :id",
    ):
        with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.role", "veterinarian")
            set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
            session.execute(text(statement), {"id": UUID(created["id"])})
        with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
            connection.execute(text(statement), {"id": UUID(created["id"])})
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "reception")
        set_context(session, "vetsys.user_id", str(data.users["reception_a"].id))
        assert session.scalars(select(PatientDocument)).all() == []


@pytest.mark.parametrize(
    "name,expected",
    [
        ("C:\\fotos\\laudo.pdf", "laudo.pdf"),
        ("../../etc/passwd", "passwd"),
        ('lau"do<>.pdf', "lau_do__.pdf"),
        ("   ", "documento"),
        ("a" * 300 + ".pdf", "a" * 200),
    ],
)
def test_file_names_are_sanitized(name: str, expected: str) -> None:
    assert safe_file_name(name) == expected


def test_supabase_storage_never_overwrites() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(409 if len(seen) > 1 else 200, json={})
        return httpx.Response(200, content=PDF)

    store = SupabaseFileStorage(
        "http://storage.test", "chave-ficticia", transport=httpx.MockTransport(handler)
    )
    store.put("clinica/paciente/doc", PDF, "application/pdf")
    with pytest.raises(BusinessConflict):
        store.put("clinica/paciente/doc", PDF, "application/pdf")
    assert store.get("clinica/paciente/doc") == PDF
    first = seen[0]
    assert first.url.path == f"/storage/v1/object/{BUCKET}/clinica/paciente/doc"
    assert first.headers["x-upsert"] == "false"
    assert first.headers["authorization"] == "Bearer chave-ficticia"
    assert "chave" not in str(first.url)
