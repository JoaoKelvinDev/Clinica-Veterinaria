from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.patients.models import Patient, TutorPatient
from app.modules.tutors.models import Tutor
from tests.conftest import DatabaseFixture


def headers(token: str = "admin_a") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def tutor(client: TestClient, token: str = "admin_a", **values: object) -> dict[str, object]:
    response = client.post(
        "/tutors", headers=headers(token), json={"name": "Tutor fictício", **values}
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def patient(client: TestClient, token: str = "admin_a", **values: object) -> dict[str, object]:
    response = client.post(
        "/patients",
        headers=headers(token),
        json={"name": "Paciente fictício", "species": "Canina", **values},
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def test_tutor_crud_search_and_soft_archive(client: TestClient, database: DatabaseFixture) -> None:
    created = tutor(
        client, phone="(86) 99999-9999", document="FICTICIO", address="Endereço fictício"
    )
    assert created["phone"] == "+5586999999999"
    assert created["whatsapp_opt_in"] is False
    found = client.get("/tutors", headers=headers(), params={"q": "(86) 99999"}).json()
    assert found["total"] == 1
    assert (
        client.patch(
            f"/tutors/{created['id']}", headers=headers(), json={"name": "Nome alterado"}
        ).status_code
        == 200
    )
    assert client.delete(f"/tutors/{created['id']}", headers=headers()).status_code == 204
    assert client.get(f"/tutors/{created['id']}", headers=headers()).status_code == 404
    assert client.get("/tutors", headers=headers()).json()["total"] == 0
    with Session(database.admin) as session:
        archived = session.get(Tutor, UUID(str(created["id"])))
        assert archived is not None and archived.deleted_at is not None


def test_consent_requires_phone_origin_and_explicit_action(client: TestClient) -> None:
    created = tutor(client)
    url = f"/tutors/{created['id']}/whatsapp-consent"
    assert (
        client.put(
            url, headers=headers(), json={"granted": True, "source": "Presencial"}
        ).status_code
        == 422
    )
    assert client.put(url, headers=headers(), json={"granted": True}).status_code == 422
    assert (
        client.patch(
            f"/tutors/{created['id']}", headers=headers(), json={"phone": "(86) 99999-9999"}
        ).status_code
        == 200
    )
    granted = client.put(url, headers=headers(), json={"granted": True, "source": "Presencial"})
    assert granted.status_code == 200
    assert granted.json()["whatsapp_opt_in_at"] is not None
    assert granted.json()["whatsapp_opt_in_source"] == "Presencial"
    changed = client.patch(
        f"/tutors/{created['id']}", headers=headers(), json={"phone": "+5511961234567"}
    )
    assert changed.status_code == 200
    assert changed.json()["whatsapp_opt_in"] is False
    assert changed.json()["whatsapp_opt_out_at"] is not None
    assert changed.json()["whatsapp_opt_in_source"] == "Presencial"


def test_archiving_tutor_revokes_consent_and_preserves_link_history(client: TestClient) -> None:
    created = tutor(
        client, phone="(86) 99999-9999", whatsapp_consent={"granted": True, "source": "Presencial"}
    )
    animal = patient(client)
    assert (
        client.post(
            f"/patients/{animal['id']}/tutors", headers=headers(), json={"tutor_id": created["id"]}
        ).status_code
        == 200
    )
    assert client.delete(f"/tutors/{created['id']}", headers=headers()).status_code == 204
    links = client.get(f"/patients/{animal['id']}/tutors", headers=headers()).json()
    assert links[0]["tutor"]["deleted_at"] is not None
    assert links[0]["tutor"]["whatsapp_opt_in"] is False


def test_patient_crud_search_and_soft_archive(
    client: TestClient, database: DatabaseFixture
) -> None:
    created = patient(client, microchip=" chip-ficticio ", estimated_age_months=12, neutered=True)
    assert created["microchip"] == "CHIP-FICTICIO"
    assert (
        client.get("/patients", headers=headers(), params={"q": "chip-ficticio"}).json()["total"]
        == 1
    )
    assert (
        client.patch(
            f"/patients/{created['id']}", headers=headers(), json={"name": "Novo nome"}
        ).status_code
        == 200
    )
    assert client.delete(f"/patients/{created['id']}", headers=headers()).status_code == 204
    assert client.get(f"/patients/{created['id']}", headers=headers()).status_code == 404
    with Session(database.admin) as session:
        archived = session.get(Patient, UUID(str(created["id"])))
        assert archived is not None and archived.deleted_at is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"birth_date": "2000-01-01", "estimated_age_months": 10},
        {"birth_date": (datetime.now(UTC).date() + timedelta(days=1)).isoformat()},
        {"estimated_age_months": -1},
        {"sex": "invalid"},
        {"name": " "},
    ],
)
def test_invalid_patient_data_is_rejected(client: TestClient, changes: dict[str, object]) -> None:
    response = client.post(
        "/patients", headers=headers(), json={"name": "Fictício", "species": "Felina", **changes}
    )
    assert response.status_code == 422
    assert client.get("/patients", headers=headers()).json()["total"] == 0


def test_microchip_unique_only_within_clinic(client: TestClient) -> None:
    first = patient(client, microchip="chip-ficticio")
    second = patient(client)
    duplicate = client.patch(
        f"/patients/{second['id']}", headers=headers(), json={"microchip": "CHIP-FICTICIO"}
    )
    assert duplicate.status_code == 409
    other = patient(client, "admin_b", microchip="chip-ficticio")
    assert other["clinic_id"] != first["clinic_id"]


def test_multiple_tutors_primary_switch_and_unlink(
    client: TestClient, database: DatabaseFixture
) -> None:
    a, b = tutor(client), tutor(client, name="Outro tutor fictício")
    animal = patient(client)
    url = f"/patients/{animal['id']}/tutors"
    first = client.post(url, headers=headers(), json={"tutor_id": a["id"]}).json()
    assert first[0]["is_primary"] is True
    assert client.post(url, headers=headers(), json={"tutor_id": b["id"]}).status_code == 200
    replaced = client.post(
        url, headers=headers(), json={"tutor_id": b["id"], "is_primary": True}
    ).json()
    assert sum(item["is_primary"] for item in replaced) == 1
    assert next(item for item in replaced if item["is_primary"])["tutor"]["id"] == b["id"]
    assert client.delete(f"{url}/{a['id']}", headers=headers()).status_code == 204
    restored = client.post(url, headers=headers(), json={"tutor_id": a["id"]}).json()
    assert len(restored) == 2
    with Session(database.admin) as session:
        rows = session.scalars(
            select(TutorPatient).where(TutorPatient.patient_id == UUID(str(animal["id"])))
        ).all()
        assert len(rows) == 2
    another = patient(client, name="Outro paciente")
    assert (
        client.post(
            f"/patients/{another['id']}/tutors", headers=headers(), json={"tutor_id": a["id"]}
        ).status_code
        == 200
    )


def test_another_clinic_cannot_be_read_changed_or_linked(client: TestClient) -> None:
    foreign_tutor = tutor(client, "admin_b")
    foreign_patient = patient(client, "admin_b")
    own_patient = patient(client)
    for kind, record in (("tutors", foreign_tutor), ("patients", foreign_patient)):
        url = f"/{kind}/{record['id']}"
        assert client.get(url, headers=headers()).status_code == 404
        assert client.patch(url, headers=headers(), json={"name": "Tentativa"}).status_code == 404
        assert client.delete(url, headers=headers()).status_code == 404
        assert client.get(f"/{kind}", headers=headers()).json()["total"] == (
            1 if kind == "patients" else 0
        )
    assert (
        client.post(
            f"/patients/{own_patient['id']}/tutors",
            headers=headers(),
            json={"tutor_id": foreign_tutor["id"]},
        ).status_code
        == 404
    )
    assert (
        client.get(f"/patients/{foreign_patient['id']}/tutors", headers=headers()).status_code
        == 404
    )


@pytest.mark.parametrize("token", ["vet_a", "assistant_a"])
def test_registry_readers_cannot_mutate(client: TestClient, token: str) -> None:
    t, p = tutor(client), patient(client)
    assert client.get("/tutors", headers=headers(token)).status_code == 200
    assert client.get("/patients", headers=headers(token)).status_code == 200
    assert (
        client.post("/tutors", headers=headers(token), json={"name": "Tentativa"}).status_code
        == 403
    )
    assert (
        client.patch(
            f"/patients/{p['id']}", headers=headers(token), json={"name": "Tentativa"}
        ).status_code
        == 403
    )
    assert client.delete(f"/tutors/{t['id']}", headers=headers(token)).status_code == 403
    assert (
        client.post(
            f"/patients/{p['id']}/tutors", headers=headers(token), json={"tutor_id": t["id"]}
        ).status_code
        == 403
    )


def test_reception_can_manage_registry(client: TestClient) -> None:
    t, p = tutor(client, "reception_a"), patient(client, "reception_a")
    assert (
        client.post(
            f"/patients/{p['id']}/tutors",
            headers=headers("reception_a"),
            json={"tutor_id": t["id"]},
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "payload", [{"clinic_id": "forged"}, {"whatsapp_opt_in": True}, {"deleted_at": "2000-01-01"}]
)
def test_tutor_rejects_server_owned_fields(client: TestClient, payload: dict[str, object]) -> None:
    assert (
        client.post("/tutors", headers=headers(), json={"name": "Fictício", **payload}).status_code
        == 422
    )


def test_search_pagination_and_literal_wildcards(client: TestClient) -> None:
    tutor(client, name="100% fictício")
    tutor(client, name="Outro fictício")
    page = client.get("/tutors", headers=headers(), params={"limit": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1
    assert client.get("/tutors", headers=headers(), params={"q": "%"}).json()["total"] == 1
    assert (
        client.get("/tutors", headers=headers(), params={"q": "' OR true --"}).json()["total"] == 0
    )
    assert client.get("/tutors", headers=headers(), params={"limit": 1000}).status_code == 422
