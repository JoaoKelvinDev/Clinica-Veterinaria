from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.errors import AccessDenied
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.records.models import AuditLog, RecordEntry
from app.modules.records.schemas import RecordEntryCreate
from app.modules.records.services import RecordService
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_registry_api import headers, patient

ENTRY = {
    "complaint": "Relato fictício do responsável",
    "general_state": "Alerta, mucosas normocoradas",
    "presumptive_diagnosis": "Diagnóstico presuntivo fictício",
}
TODAY = date.today()


def encounter(client: TestClient) -> dict[str, object]:
    p = patient(client)
    response = client.post("/encounters", headers=headers("vet_a"), json={"patient_id": p["id"]})
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def entry(client: TestClient, encounter_id: object, **values: object) -> dict[str, object]:
    response = client.post(
        f"/encounters/{encounter_id}/record-entries",
        headers=headers("vet_a"),
        json={**ENTRY, **values},
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def vaccine(**values: object) -> dict[str, object]:
    return {
        "vaccine_name": "Vacina fictícia V10",
        "batch": "LOTE-FICTICIO",
        "manufacturer": "Fabricante fictício",
        "dose": "1ª dose",
        "manufactured_on": str(TODAY - timedelta(days=60)),
        "expires_on": str(TODAY + timedelta(days=300)),
        "next_dose_on": str(TODAY + timedelta(days=21)),
        **values,
    }


def audit(database: DatabaseFixture) -> list[tuple[str, str]]:
    with Session(database.admin) as session:
        rows = session.execute(
            select(AuditLog.action, AuditLog.entity).order_by(AuditLog.created_at)
        ).all()
        return [(action, entity) for action, entity in rows]


def test_entry_records_author_location_and_audit(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    opened = encounter(client)
    created = entry(client, opened["id"], findings="Achado fictício")
    assert created["version"] == 1
    assert created["root_id"] == created["id"]
    assert created["author_name"] == data.users["vet_a"].name
    assert created["author_crmv"] == "CRMV-PI 1234"
    assert created["location"] == "Clínica fictícia A"
    record = client.get(f"/patients/{opened['patient_id']}/record", headers=headers("vet_a"))
    assert record.status_code == 200
    body = record.json()
    assert body["clinical_access"] is True
    assert [item["id"] for item in body["entries"]] == [created["id"]]
    assert [item["id"] for item in body["encounters"]] == [opened["id"]]
    assert audit(database) == [("create", "record_entry"), ("read", "patient_record")]


def test_correction_creates_version_and_preserves_previous(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    opened = encounter(client)
    first = entry(client, opened["id"])
    second = entry(
        client,
        opened["id"],
        presumptive_diagnosis="Diagnóstico corrigido",
        supersedes_id=first["id"],
        correction_reason="Erro de digitação",
    )
    assert (second["version"], second["root_id"]) == (2, first["id"])
    url = f"/encounters/{opened['id']}/record-entries"
    again = client.post(
        url,
        headers=headers("vet_a"),
        json={**ENTRY, "supersedes_id": first["id"], "correction_reason": "Outra"},
    )
    assert again.status_code == 409
    versions = client.get(f"/record-entries/{second['id']}/versions", headers=headers()).json()
    assert [(v["version"], v["presumptive_diagnosis"]) for v in versions] == [
        (1, ENTRY["presumptive_diagnosis"]),
        (2, "Diagnóstico corrigido"),
    ]
    record = client.get(f"/patients/{opened['patient_id']}/record", headers=headers()).json()
    assert [item["id"] for item in record["entries"]] == [second["id"]]
    assert ("correct", "record_entry") in audit(database)


@pytest.mark.parametrize(
    "values",
    [
        {"presumptive_diagnosis": None},
        {"complaint": ""},
        {"general_state": "   "},
        {"correction_reason": "Motivo sem registro anterior"},
        {"supersedes_id": str(uuid4())},
        {"unexpected": "x"},
    ],
)
def test_invalid_entries_are_rejected(client: TestClient, values: dict[str, object]) -> None:
    opened = encounter(client)
    payload = {**ENTRY, **values}
    response = client.post(
        f"/encounters/{opened['id']}/record-entries",
        headers=headers("vet_a"),
        json={key: value for key, value in payload.items() if value is not None},
    )
    assert response.status_code == 422


def test_correction_must_come_from_author_and_same_encounter(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    first_encounter = encounter(client)
    first = entry(client, first_encounter["id"])
    other = client.post(
        "/encounters",
        headers=headers("vet_a"),
        json={"patient_id": first_encounter["patient_id"]},
    ).json()
    moved = client.post(
        f"/encounters/{other['id']}/record-entries",
        headers=headers("vet_a"),
        json={**ENTRY, "supersedes_id": first["id"], "correction_reason": "Outro atendimento"},
    )
    assert moved.status_code == 422
    stranger = User(
        id=uuid4(),
        clinic_id=data.clinic_a.id,
        auth_id=uuid4(),
        name="Outro veterinário fictício",
        role=Role.VETERINARIAN,
        active=True,
        crmv="9999",
        crmv_state="PI",
    )
    values = RecordEntryCreate.model_validate(
        {**ENTRY, "supersedes_id": first["id"], "correction_reason": "Tentativa"}
    )
    with database.runtime.sessions.begin() as session, pytest.raises(AccessDenied):
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "veterinarian")
        set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
        service = RecordService.for_clinic(session, ClinicContext(data.clinic_a.id))
        service.add_entry(stranger, UUID(str(first_encounter["id"])), values)


@pytest.mark.parametrize("token", ["admin_a", "assistant_a", "reception_a"])
def test_only_veterinarians_write_entries_and_vaccines(client: TestClient, token: str) -> None:
    opened = encounter(client)
    response = client.post(
        f"/encounters/{opened['id']}/record-entries", headers=headers(token), json=ENTRY
    )
    assert response.status_code == 403
    response = client.post(
        f"/patients/{opened['patient_id']}/vaccines",
        headers=headers(token),
        json=vaccine(encounter_id=opened["id"]),
    )
    assert response.status_code == 403


def test_reception_sees_only_encounters(client: TestClient) -> None:
    opened = encounter(client)
    created = entry(client, opened["id"])
    record = client.get(
        f"/patients/{opened['patient_id']}/record", headers=headers("reception_a")
    ).json()
    assert record["clinical_access"] is False
    assert len(record["encounters"]) == 1
    assert record["entries"] == record["weights"] == record["vaccines"] == []
    versions = client.get(
        f"/record-entries/{created['id']}/versions", headers=headers("reception_a")
    )
    assert versions.status_code == 403
    weight = client.post(
        f"/patients/{opened['patient_id']}/weights",
        headers=headers("reception_a"),
        json={"weight_grams": 1000},
    )
    assert weight.status_code == 403


def test_weights_by_assistant_with_correction(client: TestClient) -> None:
    opened = encounter(client)
    url = f"/patients/{opened['patient_id']}/weights"
    first = client.post(url, headers=headers("assistant_a"), json={"weight_grams": 12500})
    assert first.status_code == 201, first.text
    wrong = client.post(
        url,
        headers=headers("vet_a"),
        json={"weight_grams": 12400, "supersedes_id": first.json()["id"], "correction_reason": "x"},
    )
    assert wrong.status_code == 422
    other_author = client.post(
        url,
        headers=headers("vet_a"),
        json={
            "weight_grams": 12400,
            "supersedes_id": first.json()["id"],
            "correction_reason": "Balança",
        },
    )
    assert other_author.status_code == 403
    fixed = client.post(
        url,
        headers=headers("assistant_a"),
        json={
            "weight_grams": 12400,
            "supersedes_id": first.json()["id"],
            "correction_reason": "Balança sem tara",
        },
    )
    assert fixed.status_code == 201
    assert client.post(url, headers=headers("vet_a"), json={"weight_grams": 0}).status_code == 422
    record = client.get(f"/patients/{opened['patient_id']}/record", headers=headers()).json()
    assert [w["weight_grams"] for w in record["weights"]] == [12400]


def test_vaccine_requires_cfmv_fields_and_valid_dates(client: TestClient) -> None:
    opened = encounter(client)
    url = f"/patients/{opened['patient_id']}/vaccines"
    created = client.post(url, headers=headers("vet_a"), json=vaccine(encounter_id=opened["id"]))
    assert created.status_code == 201, created.text
    assert created.json()["author_crmv"] == "CRMV-PI 1234"
    for field in ("batch", "manufacturer", "dose", "manufactured_on", "expires_on"):
        payload = vaccine(encounter_id=opened["id"])
        del payload[field]
        assert client.post(url, headers=headers("vet_a"), json=payload).status_code == 422
    for values in (
        {"expires_on": str(TODAY - timedelta(days=1))},
        {"manufactured_on": str(TODAY + timedelta(days=400))},
        {"next_dose_on": str(TODAY)},
    ):
        response = client.post(
            url, headers=headers("vet_a"), json=vaccine(encounter_id=opened["id"], **values)
        )
        assert response.status_code == 422, values
    other = encounter(client)
    response = client.post(url, headers=headers("vet_a"), json=vaccine(encounter_id=other["id"]))
    assert response.status_code == 422
    fixed = client.post(
        url,
        headers=headers("vet_a"),
        json=vaccine(
            encounter_id=opened["id"],
            batch="LOTE-CORRIGIDO",
            supersedes_id=created.json()["id"],
            correction_reason="Lote anotado errado",
        ),
    )
    assert fixed.status_code == 201
    record = client.get(f"/patients/{opened['patient_id']}/record", headers=headers()).json()
    assert [v["batch"] for v in record["vaccines"]] == ["LOTE-CORRIGIDO"]


def test_other_clinic_cannot_reach_records(client: TestClient) -> None:
    opened = encounter(client)
    created = entry(client, opened["id"])
    other = headers("admin_b")
    assert client.get(f"/patients/{opened['patient_id']}/record", headers=other).status_code == 404
    assert client.get(f"/record-entries/{created['id']}/versions", headers=other).status_code == 404


def test_database_keeps_records_append_only_and_hidden_from_reception(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    opened = encounter(client)
    created = entry(client, opened["id"])
    entry_id = UUID(str(created["id"]))
    for statement in (
        "UPDATE vetsys.record_entries SET complaint = 'alterado' WHERE id = :id",
        "DELETE FROM vetsys.record_entries WHERE id = :id",
    ):
        with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.role", "veterinarian")
            set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
            session.execute(text(statement), {"id": entry_id})
        # Mesmo o papel administrativo do banco é barrado pelo gatilho.
        with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
            connection.execute(text(statement), {"id": entry_id})
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "reception")
        set_context(session, "vetsys.user_id", str(data.users["reception_a"].id))
        assert session.scalars(select(RecordEntry)).all() == []
    with Session(database.admin) as session:
        stored = session.get(RecordEntry, entry_id)
        assert stored is not None
        assert stored.complaint == ENTRY["complaint"]


def test_database_rejects_inconsistent_versions(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    opened = encounter(client)
    first = entry(client, opened["id"])
    with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "veterinarian")
        set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
        new_id = uuid4()
        session.add(
            RecordEntry(
                id=new_id,
                clinic_id=data.clinic_a.id,
                patient_id=UUID(str(opened["patient_id"])),
                encounter_id=UUID(str(opened["id"])),
                root_id=new_id,
                version=5,
                supersedes_id=UUID(str(first["id"])),
                correction_reason="Versão inventada",
                author_id=data.users["vet_a"].id,
                author_name="x",
                author_crmv="x",
                location="x",
                **ENTRY,
            )
        )
        session.flush()
