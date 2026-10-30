from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.repositories import ClinicContext
from app.modules.clinics.models import Role, User
from app.modules.scheduling.models import Appointment, Encounter
from app.modules.scheduling.repositories import AppointmentRepository, EncounterRepository
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_registry_api import headers, patient


def book(
    client: TestClient,
    data: FixtureData,
    *,
    start: str = "2030-01-01T09:00:00-03:00",
    end: str = "2030-01-01T10:00:00-03:00",
    token: str = "admin_a",
) -> dict[str, object]:
    p = patient(client, token)
    response = client.post(
        "/appointments",
        headers=headers(token),
        json={
            "patient_id": p["id"],
            "veterinarian_id": str(data.users["vet_a"].id),
            "starts_at": start,
            "ends_at": end,
            "kind": "Consulta fictícia",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


def test_schedule_filter_reschedule_and_confirmation(client: TestClient, data: FixtureData) -> None:
    created = book(client, data)
    assert created["status"] == "scheduled"
    assert created["starts_at"] == "2030-01-01T12:00:00Z"
    url = f"/appointments/{created['id']}"
    assert client.get("/appointments?day=2030-01-01", headers=headers()).json()["total"] == 1
    assert (
        client.get(
            f"/appointments?day=2030-01-01&veterinarian_id={data.users['admin_a'].id}",
            headers=headers(),
        ).json()["total"]
        == 0
    )
    assert client.get("/appointments?day=2030-01-02", headers=headers()).json()["total"] == 0
    assert (
        client.put(
            f"{url}/status", headers=headers("reception_a"), json={"status": "confirmed"}
        ).json()["status"]
        == "confirmed"
    )
    changed = client.patch(
        url,
        headers=headers(),
        json={"starts_at": "2030-01-01T10:00:00-03:00", "ends_at": "2030-01-01T11:00:00-03:00"},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "scheduled"


@pytest.mark.parametrize(
    "start,end", [("09:00", "10:00"), ("09:30", "10:30"), ("08:30", "09:30"), ("08:00", "11:00")]
)
def test_overlaps_rejected_and_reschedule_rolls_back(
    client: TestClient, data: FixtureData, start: str, end: str
) -> None:
    first = book(client, data)
    second = book(client, data, start="2030-01-01T10:00:00-03:00", end="2030-01-01T11:00:00-03:00")
    response = client.patch(
        f"/appointments/{second['id']}",
        headers=headers(),
        json={"starts_at": f"2030-01-01T{start}:00-03:00", "ends_at": f"2030-01-01T{end}:00-03:00"},
    )
    assert response.status_code == 409
    assert (
        client.get(f"/appointments/{second['id']}", headers=headers()).json()["starts_at"]
        == second["starts_at"]
    )
    assert first["id"] != second["id"]


@pytest.mark.parametrize("terminal", ["cancelled", "no_show"])
def test_cancellation_or_no_show_releases_slot_without_deleting(
    client: TestClient, data: FixtureData, database: DatabaseFixture, terminal: str
) -> None:
    first = book(client, data)
    url = f"/appointments/{first['id']}"
    assert (
        client.put(f"{url}/status", headers=headers(), json={"status": terminal}).status_code == 200
    )
    assert book(client, data)["id"] != first["id"]
    assert client.patch(url, headers=headers(), json={"kind": "Tentativa"}).status_code == 409
    with Session(database.admin) as session:
        assert session.get(Appointment, UUID(str(first["id"]))) is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"ends_at": "2030-01-01T08:00:00-03:00"},
        {"starts_at": "2030-01-01T09:00:00"},
        {"kind": " "},
        {"patient_id": None},
        {"clinic_id": "forged"},
        {"status": "completed"},
        {},
    ],
)
def test_invalid_appointment_patch(
    client: TestClient, data: FixtureData, changes: dict[str, object]
) -> None:
    created = book(client, data)
    assert (
        client.patch(f"/appointments/{created['id']}", headers=headers(), json=changes).status_code
        == 422
    )


def test_day_is_fortaleza_and_can_include_appointment_crossing_midnight(
    client: TestClient, data: FixtureData
) -> None:
    book(client, data, start="2030-01-02T02:30:00Z", end="2030-01-02T03:30:00Z")
    assert client.get("/appointments?day=2030-01-01", headers=headers()).json()["total"] == 1
    assert client.get("/appointments?day=2030-01-02", headers=headers()).json()["total"] == 1


def test_start_complete_idempotence_and_frozen_identity(
    client: TestClient, data: FixtureData
) -> None:
    created = book(client, data)
    url = f"/appointments/{created['id']}"
    started = client.post(f"{url}/start", headers=headers("vet_a"))
    assert started.status_code == 200, started.text
    encounter = started.json()
    assert encounter["veterinarian_id"] == str(data.users["vet_a"].id)
    assert client.post(f"{url}/start", headers=headers("vet_a")).json()["id"] == encounter["id"]
    assert client.get(url, headers=headers()).json()["status"] == "in_progress"
    assert client.patch(url, headers=headers(), json={"kind": "Tentativa"}).status_code == 409
    assert (
        client.put(f"{url}/status", headers=headers(), json={"status": "cancelled"}).status_code
        == 409
    )
    completed = client.post(f"/encounters/{encounter['id']}/complete", headers=headers("vet_a"))
    assert completed.status_code == 200
    assert completed.json()["completed_at"] is not None
    assert (
        client.post(f"/encounters/{encounter['id']}/complete", headers=headers("vet_a")).json()[
            "completed_at"
        ]
        == completed.json()["completed_at"]
    )
    assert client.get(url, headers=headers()).json()["status"] == "completed"
    assert client.post(f"{url}/start", headers=headers("vet_a")).status_code == 409


@pytest.mark.parametrize("token", ["admin_a", "reception_a", "assistant_a"])
def test_only_assigned_vet_can_start_or_complete(
    client: TestClient, data: FixtureData, token: str
) -> None:
    created = book(client, data)
    url = f"/appointments/{created['id']}"
    assert client.post(f"{url}/start", headers=headers(token)).status_code == 403
    started = client.post(f"{url}/start", headers=headers("vet_a")).json()
    assert (
        client.post(f"/encounters/{started['id']}/complete", headers=headers(token)).status_code
        == 403
    )
    assert (
        client.post(
            "/encounters", headers=headers(token), json={"patient_id": created["patient_id"]}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("token", ["vet_a", "assistant_a"])
def test_readers_cannot_manage_bookings(client: TestClient, data: FixtureData, token: str) -> None:
    created = book(client, data)
    assert client.get("/appointments?day=2030-01-01", headers=headers(token)).status_code == 200
    assert client.get("/veterinarians", headers=headers(token)).json()[0]["id"] == str(
        data.users["vet_a"].id
    )
    assert (
        client.patch(
            f"/appointments/{created['id']}", headers=headers(token), json={"kind": "Tentativa"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/appointments/{created['id']}/status",
            headers=headers(token),
            json={"status": "confirmed"},
        ).status_code
        == 403
    )


def test_walk_in_and_archived_patient_preserve_history(
    client: TestClient, data: FixtureData
) -> None:
    p = patient(client)
    opened = client.post("/encounters", headers=headers("vet_a"), json={"patient_id": p["id"]})
    assert opened.status_code == 201
    item = opened.json()
    assert item["appointment_id"] is None
    day = datetime.now(UTC).astimezone(ZoneInfo("America/Fortaleza")).date()
    assert client.get(f"/encounters?day={day}", headers=headers()).json()["total"] == 1
    assert client.delete(f"/patients/{p['id']}", headers=headers()).status_code == 204
    assert client.get(f"/encounters/{item['id']}", headers=headers()).status_code == 200
    assert (
        client.post(
            "/encounters", headers=headers("vet_a"), json={"patient_id": p["id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(f"/encounters/{item['id']}/complete", headers=headers("vet_a")).status_code
        == 200
    )


def test_cross_clinic_access_and_foreign_references_are_blocked(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    created = book(client, data)
    opened = client.post(f"/appointments/{created['id']}/start", headers=headers("vet_a")).json()
    assert (
        client.get("/appointments?day=2030-01-01", headers=headers("admin_b")).json()["total"] == 0
    )
    for path in (f"/appointments/{created['id']}", f"/encounters/{opened['id']}"):
        assert client.get(path, headers=headers("admin_b")).status_code == 404
    assert (
        client.post(f"/appointments/{created['id']}/start", headers=headers("admin_b")).status_code
        == 404
    )
    assert (
        client.post(f"/encounters/{opened['id']}/complete", headers=headers("admin_b")).status_code
        == 404
    )
    foreign = patient(client, "admin_b")
    response = client.post(
        "/appointments",
        headers=headers(),
        json={
            "patient_id": foreign["id"],
            "veterinarian_id": str(data.users["vet_a"].id),
            "starts_at": "2030-01-02T09:00:00Z",
            "ends_at": "2030-01-02T10:00:00Z",
            "kind": "Teste",
        },
    )
    assert response.status_code == 404
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_b.id))
        set_context(session, "vetsys.role", "admin")
        context = ClinicContext(data.clinic_b.id)
        assert AppointmentRepository(session, context).get(UUID(str(created["id"]))) is None
        assert EncounterRepository(session, context).get(UUID(opened["id"])) is None
        assert list(session.scalars(select(Appointment))) == []
        assert list(session.scalars(select(Encounter))) == []
    with database.runtime.sessions.begin() as session:
        assert list(session.scalars(select(Appointment))) == []
        assert list(session.scalars(select(Encounter))) == []


def test_race_for_same_slot_returns_one_conflict(
    client: TestClient, data: FixtureData, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = patient(client)
    barrier = Barrier(2)
    original = AppointmentRepository.overlaps

    def simultaneous(self: AppointmentRepository, item: Appointment) -> bool:
        result = original(self, item)
        barrier.wait(timeout=10)
        return result

    monkeypatch.setattr(AppointmentRepository, "overlaps", simultaneous)
    payload = {
        "patient_id": p["id"],
        "veterinarian_id": str(data.users["vet_a"].id),
        "starts_at": "2030-01-01T09:00:00Z",
        "ends_at": "2030-01-01T10:00:00Z",
        "kind": "Concorrência fictícia",
    }

    def create(_: int) -> int:
        return int(client.post("/appointments", headers=headers(), json=payload).status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(create, range(2))) == [201, 409]


def test_database_prevents_cross_tenant_encounter_and_identity_changes(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    created = book(client, data)
    opened = client.post(f"/appointments/{created['id']}/start", headers=headers("vet_a")).json()
    for statement in (
        "DELETE FROM vetsys.encounters WHERE id = :id",
        "UPDATE vetsys.encounters SET patient_id = :id WHERE id = :id",
    ):
        with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.role", "veterinarian")
            set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
            session.execute(text(statement), {"id": UUID(opened["id"])})
    with Session(database.admin) as session, pytest.raises(IntegrityError):
        session.add(
            Encounter(
                clinic_id=data.clinic_b.id,
                patient_id=UUID(str(created["patient_id"])),
                veterinarian_id=data.users["vet_a"].id,
                started_at=datetime.now(UTC),
            )
        )
        session.flush()


def test_concurrent_start_and_completion_do_not_duplicate_or_overwrite(
    client: TestClient, data: FixtureData
) -> None:
    created = book(client, data)

    def start(_: int) -> dict[str, object]:
        response = client.post(f"/appointments/{created['id']}/start", headers=headers("vet_a"))
        assert response.status_code == 200
        result: dict[str, object] = response.json()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        started = list(executor.map(start, range(2)))
    assert started[0]["id"] == started[1]["id"]

    def complete(_: int) -> dict[str, object]:
        response = client.post(f"/encounters/{started[0]['id']}/complete", headers=headers("vet_a"))
        assert response.status_code == 200, response.text
        result: dict[str, object] = response.json()
        return result

    with ThreadPoolExecutor(max_workers=2) as executor:
        completed = list(executor.map(complete, range(2)))
    assert completed[0]["completed_at"] == completed[1]["completed_at"]


def test_active_veterinarian_required_and_other_vet_cannot_operate(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    created = book(client, data)
    p = patient(client)
    url = f"/appointments/{created['id']}"
    other_id = uuid4()
    with Session(database.admin) as session:
        session.add(
            User(
                id=other_id,
                clinic_id=data.clinic_a.id,
                auth_id=uuid4(),
                name="Outro veterinário fictício",
                role=Role.VETERINARIAN,
                active=True,
                crmv="4321",
                crmv_state="PI",
            )
        )
        session.commit()
    assert (
        client.patch(url, headers=headers(), json={"veterinarian_id": str(other_id)}).status_code
        == 200
    )
    assert client.post(f"{url}/start", headers=headers("vet_a")).status_code == 403
    with Session(database.admin) as session:
        vet = session.get(User, data.users["vet_a"].id)
        assert vet is not None
        vet.active = False
        session.commit()
    response = client.post(
        "/appointments",
        headers=headers(),
        json={
            "patient_id": p["id"],
            "veterinarian_id": str(data.users["vet_a"].id),
            "starts_at": "2030-01-02T09:00:00Z",
            "ends_at": "2030-01-02T10:00:00Z",
            "kind": "Consulta",
        },
    )
    assert response.status_code == 404
    assert client.get(url, headers=headers()).status_code == 200
    assert client.post(f"{url}/start", headers=headers("vet_a")).status_code == 403
