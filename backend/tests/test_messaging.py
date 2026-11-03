from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.messaging.models import Message, ReminderJob
from app.modules.messaging.planner import within_window
from app.modules.messaging.services import classify
from app.providers.messaging import MockMessagingProvider
from app.worker import run_once
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_records import ENTRY
from tests.test_registry_api import headers, patient, tutor

TZ = ZoneInfo("America/Fortaleza")
PHONE = "+5586999990000"


def family(
    client: TestClient, *, opt_in: bool = True, phone: str = "(86) 99999-0000"
) -> dict[str, Any]:
    p = patient(client, name="Thor fictício")
    t = tutor(client, name="Maria Fictícia Souza", phone=phone)
    if opt_in:
        consent = client.put(
            f"/tutors/{t['id']}/whatsapp-consent",
            headers=headers(),
            json={"granted": True, "source": "Ficha de cadastro no balcão da Clínica fictícia A"},
        )
        assert consent.status_code == 200, consent.text
    link = client.post(
        f"/patients/{p['id']}/tutors",
        headers=headers(),
        json={"tutor_id": t["id"], "is_primary": True},
    )
    assert link.status_code in {200, 201}, link.text
    return {"patient": p, "tutor": t}


def book(client: TestClient, data: FixtureData, patient_id: object, start: str) -> dict[str, Any]:
    response = client.post(
        "/appointments",
        headers=headers(),
        json={
            "patient_id": patient_id,
            "veterinarian_id": str(data.users["vet_a"].id),
            "starts_at": start,
            "ends_at": (datetime.fromisoformat(start) + timedelta(minutes=30)).isoformat(),
            "kind": "Consulta fictícia",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def jobs(database: DatabaseFixture) -> list[ReminderJob]:
    with Session(database.admin, expire_on_commit=False) as session:
        return list(session.scalars(select(ReminderJob).order_by(ReminderJob.created_at)))


def outbound(database: DatabaseFixture) -> list[Message]:
    with Session(database.admin, expire_on_commit=False) as session:
        return list(
            session.scalars(
                select(Message).where(Message.direction == "outbound").order_by(Message.created_at)
            )
        )


@pytest.mark.parametrize(
    "local,expected",
    [("10:00", "10:00"), ("07:00", "08:00"), ("20:30", "08:00+1"), ("19:59", "19:59")],
)
def test_reminders_only_between_8_and_20(local: str, expected: str) -> None:
    moment = datetime.combine(date(2030, 1, 10), datetime.strptime(local, "%H:%M").time(), TZ)
    result = within_window(moment.astimezone(UTC)).astimezone(TZ)
    hour, _, plus = expected.partition("+")
    assert result.strftime("%H:%M") == hour
    assert result.date() == date(2030, 1, 10) + timedelta(days=int(plus or 0))


@pytest.mark.parametrize(
    "body,intent",
    [
        ("Confirmo", "confirm"),
        ("  sim! ", "confirm"),
        ("CANCELAR", "cancel"),
        ("Não posso", "cancel"),
        ("sair", "opt_out"),
        ("Posso levar outro dia?", "unknown"),
        ("confirmo e quero saber da vacina", "unknown"),
    ],
)
def test_reply_classification(body: str, intent: str) -> None:
    assert classify(body) == intent


def test_booking_plans_confirmation_and_status_changes_replan(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    f = family(client)
    created = book(client, data, f["patient"]["id"], "2030-01-10T09:00:00-03:00")
    planned = jobs(database)
    assert [(j.kind, j.status) for j in planned] == [("appointment_confirmation", "pending")]
    assert planned[0].due_at.astimezone(TZ) == datetime(2030, 1, 9, 9, 0, tzinfo=TZ)
    url = f"/appointments/{created['id']}"
    client.put(f"{url}/status", headers=headers(), json={"status": "confirmed"})
    by_kind = {j.kind: j.status for j in jobs(database)}
    assert by_kind == {"appointment_confirmation": "cancelled", "appointment_reminder": "pending"}
    reminder = next(j for j in jobs(database) if j.kind == "appointment_reminder")
    assert reminder.due_at.astimezone(TZ) == datetime(2030, 1, 10, 8, 0, tzinfo=TZ)
    client.patch(
        url,
        headers=headers(),
        json={
            "starts_at": "2030-01-11T15:00:00-03:00",
            "ends_at": "2030-01-11T15:30:00-03:00",
        },
    )
    pending = [j for j in jobs(database) if j.status == "pending"]
    assert [(j.kind, j.event_at.astimezone(TZ).day) for j in pending] == [
        ("appointment_confirmation", 11)
    ]
    client.put(f"{url}/status", headers=headers(), json={"status": "cancelled"})
    assert not [j for j in jobs(database) if j.status == "pending"]


def test_worker_sends_only_with_consent_and_without_clinical_detail(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    allowed = family(client)
    blocked = family(client, opt_in=False, phone="(86) 98888-0000")
    book(client, data, allowed["patient"]["id"], "2030-01-10T09:00:00-03:00")
    book(client, data, blocked["patient"]["id"], "2030-01-10T10:00:00-03:00")
    provider = MockMessagingProvider()
    now = datetime(2030, 1, 9, 12, 0, tzinfo=TZ)
    result = run_once(database.runtime, provider, now)
    assert (result.sent, result.skipped) == (1, 1)
    assert len(provider.sent) == 1
    phone, body = provider.sent[0]
    assert phone == PHONE
    assert "Olá, Maria!" in body and "Thor fictício" in body and "10/01 às 09:00" in body
    assert "Clínica fictícia A" in body and "SAIR" in body
    skipped = next(j for j in jobs(database) if j.status == "skipped")
    assert skipped.outcome is not None and "autorização" in skipped.outcome
    # Executar de novo não reenvia.
    assert run_once(database.runtime, provider, now).sent == 0
    assert len(outbound(database)) == 1


def test_worker_skips_events_that_already_changed(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    f = family(client)
    created = book(client, data, f["patient"]["id"], "2030-01-10T09:00:00-03:00")
    provider = MockMessagingProvider()
    # A consulta já passou quando o worker roda.
    after = datetime(2030, 1, 10, 10, 0, tzinfo=TZ)
    assert run_once(database.runtime, provider, after).skipped == 1
    assert provider.sent == []
    assert created["status"] == "scheduled"


def test_vaccine_and_follow_up_reminders(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    f = family(client)
    opened = client.post(
        "/encounters", headers=headers("vet_a"), json={"patient_id": f["patient"]["id"]}
    ).json()
    today = datetime.now(TZ).date()
    next_dose = today + timedelta(days=30)
    vaccine = client.post(
        f"/patients/{f['patient']['id']}/vaccines",
        headers=headers("vet_a"),
        json={
            "encounter_id": opened["id"],
            "vaccine_name": "Antirrábica fictícia",
            "batch": "L-1",
            "manufacturer": "Fabricante fictício",
            "dose": "Dose única",
            "manufactured_on": str(today - timedelta(days=30)),
            "expires_on": str(today + timedelta(days=300)),
            "next_dose_on": str(next_dose),
        },
    ).json()
    corrected = client.post(
        f"/patients/{f['patient']['id']}/vaccines",
        headers=headers("vet_a"),
        json={
            "encounter_id": opened["id"],
            "vaccine_name": "Antirrábica fictícia",
            "batch": "L-2",
            "manufacturer": "Fabricante fictício",
            "dose": "Dose única",
            "manufactured_on": str(today - timedelta(days=30)),
            "expires_on": str(today + timedelta(days=300)),
            "next_dose_on": str(next_dose + timedelta(days=1)),
            "supersedes_id": vaccine["id"],
            "correction_reason": "Data da revacinação errada",
        },
    )
    assert corrected.status_code == 201
    entry = client.post(
        f"/encounters/{opened['id']}/record-entries",
        headers=headers("vet_a"),
        json={**ENTRY, "follow_up_on": str(today + timedelta(days=10))},
    )
    assert entry.status_code == 201, entry.text
    past = client.post(
        f"/encounters/{opened['id']}/record-entries",
        headers=headers("vet_a"),
        json={**ENTRY, "follow_up_on": str(today - timedelta(days=1))},
    )
    assert past.status_code == 422
    states = sorted((j.kind, j.status) for j in jobs(database))
    assert states == [("follow_up", "pending"), ("vaccine", "cancelled"), ("vaccine", "pending")]
    vaccine_job = next(j for j in jobs(database) if j.kind == "vaccine" and j.status == "pending")
    assert vaccine_job.due_at.astimezone(TZ).date() == next_dose + timedelta(days=1 - 7)
    provider = MockMessagingProvider()
    run_once(database.runtime, provider, vaccine_job.due_at + timedelta(minutes=1))
    texts = [body for _, body in provider.sent]
    assert any("reforço de vacina" in t for t in texts)
    assert not any("Antirrábica" in t or "L-2" in t for t in texts)


def test_replies_confirm_cancel_opt_out_and_attention(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    f = family(client)
    created = book(client, data, f["patient"]["id"], "2030-01-10T09:00:00-03:00")
    run_once(database.runtime, MockMessagingProvider(), datetime(2030, 1, 9, 12, tzinfo=TZ))

    def reply(body: str, token: str = "reception_a", provider_id: str | None = None) -> object:
        return client.post(
            "/messaging/mock-inbound",
            headers=headers(token),
            json={"phone": "(86) 99999-0000", "body": body, "provider_message_id": provider_id},
        )

    assert reply("confirmo", token="vet_a").status_code == 403  # type: ignore[attr-defined]
    first = reply("Confirmo", provider_id="mock-in-1")
    assert first.status_code == 201  # type: ignore[attr-defined]
    assert first.json()["intent"] == "confirm"  # type: ignore[attr-defined]
    url = f"/appointments/{created['id']}"
    assert client.get(url, headers=headers()).json()["status"] == "confirmed"
    acks = [m.body for m in outbound(database) if m.reminder_job_id is None]
    assert acks == ["Consulta confirmada. Obrigado!"]
    # A mesma mensagem recebida de novo não tem novo efeito.
    reply("Confirmo", provider_id="mock-in-1")
    assert len([m for m in outbound(database) if m.reminder_job_id is None]) == 1
    question = reply("Posso levar a ração dele?").json()  # type: ignore[attr-defined]
    assert question["needs_attention"] is True
    overview = client.get("/messaging", headers=headers()).json()
    assert [m["id"] for m in overview["attention"]] == [question["id"]]
    handled = client.post(f"/messages/{question['id']}/handled", headers=headers())
    assert handled.status_code == 200
    assert client.get("/messaging", headers=headers()).json()["attention"] == []
    reply("cancelar")
    assert client.get(url, headers=headers()).json()["status"] == "cancelled"
    reply("SAIR")
    consent = client.get(f"/tutors/{f['tutor']['id']}", headers=headers()).json()
    assert consent["whatsapp_opt_in"] is False


def test_unknown_phone_and_other_clinic_are_isolated(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    f = family(client)
    book(client, data, f["patient"]["id"], "2030-01-10T09:00:00-03:00")
    run_once(database.runtime, MockMessagingProvider(), datetime(2030, 1, 9, 12, tzinfo=TZ))
    stranger = client.post(
        "/messaging/mock-inbound",
        headers=headers("admin_b"),
        json={"phone": "(86) 99999-0000", "body": "confirmo"},
    ).json()
    # Na outra clínica esse telefone não é de nenhum tutor: vai para a equipe, sem efeito.
    assert stranger["tutor_id"] is None and stranger["needs_attention"] is True
    other = client.get("/messaging", headers=headers("admin_b")).json()
    assert [m["id"] for m in other["messages"]] == [stranger["id"]]
    assert other["upcoming"] == []
    mine = client.get("/messaging", headers=headers("reception_a")).json()
    assert all(m["id"] != stranger["id"] for m in mine["messages"])
    assert UUID(mine["messages"][0]["id"])


def test_dispatch_now_is_for_reception_or_admin(client: TestClient) -> None:
    assert client.post("/messaging/dispatch-now", headers=headers("vet_a")).status_code == 403
    result = client.post("/messaging/dispatch-now", headers=headers("reception_a"))
    assert result.status_code == 200
    assert result.json() == {"sent": 0, "skipped": 0, "failed": 0}
