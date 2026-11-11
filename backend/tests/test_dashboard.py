from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, tzinfo
from decimal import Decimal
from threading import Event
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.errors import AccessDenied
from app.core.repositories import ClinicContext
from app.modules.billing.schemas import FinancialSummary
from app.modules.clinics.models import Role, User
from app.modules.dashboard.services import DashboardService
from app.modules.inventory.models import Product
from app.modules.inventory.repositories import ProductRepository
from app.modules.inventory.schemas import InventoryAlerts
from app.modules.inventory.services import InventoryService
from app.modules.messaging.models import Message
from app.modules.messaging.schemas import MessagingSummary
from app.modules.scheduling.models import Appointment, AppointmentStatus, Encounter
from app.modules.scheduling.schemas import ScheduleSummary
from app.modules.scheduling.services import SchedulingService, day_bounds
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_billing import entry
from tests.test_inventory import lot, post, product
from tests.test_registry_api import headers, patient


def today() -> date:
    return datetime.now(ZoneInfo("America/Fortaleza")).date()


def dashboard(client: TestClient, token: str = "admin_a") -> dict[str, Any]:
    response = client.get("/dashboard", headers=headers(token))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return dict(response.json())


@pytest.mark.parametrize("token", ["admin_a", "reception_a", "vet_a", "assistant_a"])
def test_empty_dashboard_and_financial_permissions(client: TestClient, token: str) -> None:
    result = dashboard(client, token)
    assert result["day"] == str(today())
    assert result["timezone"] == "America/Fortaleza"
    assert all(value == 0 for value in result["scheduling"].values())
    assert result["messaging"] == {"needs_attention": 0, "simulated": True}
    assert result["inventory"] == {"low_stock_products": 0, "expired_lots": 0, "expiring_lots": 0}
    if token in {"vet_a", "assistant_a"}:
        assert result["financial"] is None
    else:
        assert result["financial"] == {
            "income_cents": "0",
            "expense_cents": "0" if token == "admin_a" else None,
            "difference_cents": "0" if token == "admin_a" else None,
        }


@pytest.mark.parametrize(
    "token,status",
    [(None, 401), ("invalid", 401), ("inactive_a", 403), ("deleted_a", 403), ("unassigned", 403)],
)
def test_requires_active_authenticated_user(
    client: TestClient, token: str | None, status: int
) -> None:
    assert client.get("/dashboard", headers=headers(token) if token else {}).status_code == status


def test_all_appointment_statuses_and_open_encounters_beyond_first_page(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    p = UUID(str(patient(client)["id"]))
    start, end = day_bounds(today())
    statuses = list(AppointmentStatus)
    with Session(database.admin) as session, session.begin():
        for index in range(125):
            at = start + timedelta(minutes=5 * index)
            session.add(
                Appointment(
                    clinic_id=data.clinic_a.id,
                    patient_id=p,
                    veterinarian_id=data.users["vet_a"].id,
                    starts_at=at,
                    ends_at=at + timedelta(minutes=4),
                    kind="Consulta fictícia",
                    status=statuses[index % len(statuses)].value,
                )
            )
        session.add(
            Appointment(
                clinic_id=data.clinic_a.id,
                patient_id=p,
                veterinarian_id=data.users["vet_a"].id,
                starts_at=end,
                ends_at=end + timedelta(minutes=4),
                kind="Amanhã fictício",
            )
        )
        for index in range(17):
            at = start - timedelta(days=2, minutes=index)
            session.add(
                Encounter(
                    clinic_id=data.clinic_a.id,
                    patient_id=p,
                    veterinarian_id=data.users["vet_a"].id,
                    started_at=at,
                    completed_at=at + timedelta(hours=1) if index < 5 else None,
                )
            )
    counts = dashboard(client)["scheduling"]
    assert counts["appointments_total"] == 125
    assert counts["open_encounters"] == 12
    assert {
        key: value
        for key, value in counts.items()
        if key not in {"appointments_total", "open_encounters"}
    } == {
        status.value: sum(i % 6 == index for i in range(125))
        for index, status in enumerate(statuses)
    }


def test_attention_counts_all_pending_and_excludes_handled(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    ids: list[UUID] = []
    with Session(database.admin) as session, session.begin():
        for _ in range(73):
            identity = uuid4()
            ids.append(identity)
            session.add(
                Message(
                    id=identity,
                    clinic_id=data.clinic_a.id,
                    direction="inbound",
                    status="received",
                    provider="mock",
                    provider_message_id=str(uuid4()),
                    phone="+5586999999999",
                    body="Resposta fictícia privada",
                    needs_attention=True,
                )
            )
    for identity in ids[:2]:
        assert client.post(f"/messages/{identity}/handled", headers=headers()).status_code == 200
    result = dashboard(client)
    assert result["messaging"]["needs_attention"] == 71
    assert "Resposta fictícia privada" not in str(result)
    assert "+5586999999999" not in str(result)


def test_inventory_counts_all_products_and_exact_validity_boundaries(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    with Session(database.admin) as session, session.begin():
        for index in range(24):
            session.add(
                Product(
                    clinic_id=data.clinic_a.id,
                    name=f"Sem saldo fictício {index}",
                    unit="un",
                    minimum_stock=Decimal("1"),
                    track_expiry=False,
                )
            )
    p = product(client, minimum_stock="2.000")
    for code, days, quantity in [
        ("EXPIRED", -1, "5.000"),
        ("TODAY", 0, "1.000"),
        ("LIMIT", 30, "0.500"),
        ("LATER", 31, "0.500"),
    ]:
        p = lot(client, p, code, days)
        selected = next(item for item in p["lots"] if item["code"] == code)
        p = post(
            client,
            p,
            "adjustments",
            lot_id=selected["id"],
            quantity=quantity,
            reason="Saldo fictício para resumo",
        )
    p = lot(client, p, "EMPTY-EXPIRED", -2)
    archived = product(client, minimum_stock="100.000")
    post(client, archived, "archive")
    result = dashboard(client)["inventory"]
    assert result == {"low_stock_products": 24, "expired_lots": 1, "expiring_lots": 2}
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        repo = ProductRepository(session, ClinicContext(data.clinic_b.id))
        assert repo.alert_counts(today(), today() + timedelta(days=30)) == (0, 0, 0)


def test_financial_month_totals_and_reversals_never_leak_to_other_roles(client: TestClient) -> None:
    first = entry(client, amount_cents=1)
    for _ in range(24):
        entry(client, amount_cents=1)
    expense = entry(client, kind="expense", amount_cents=5)
    entry(client, amount_cents=999, occurred_on=str(today().replace(day=1) - timedelta(days=1)))
    assert dashboard(client)["financial"] == {
        "income_cents": "25",
        "expense_cents": "5",
        "difference_cents": "20",
    }
    assert dashboard(client, "reception_a")["financial"] == {
        "income_cents": "25",
        "expense_cents": None,
        "difference_cents": None,
    }
    assert dashboard(client, "vet_a")["financial"] is None
    assert dashboard(client, "assistant_a")["financial"] is None
    for original in [first, expense]:
        assert (
            client.post(
                f"/financial/entries/{original['id']}/reverse",
                headers=headers(),
                json={"reason": "Correção fictícia"},
            ).status_code
            == 201
        )
    assert dashboard(client)["financial"] == {
        "income_cents": "24",
        "expense_cents": "0",
        "difference_cents": "24",
    }


def test_every_summary_respects_clinic_even_with_client_supplied_context(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    p = UUID(str(patient(client, token="admin_b")["id"]))
    start, _ = day_bounds(today())
    with Session(database.admin) as session, session.begin():
        vet = User(
            id=uuid4(),
            clinic_id=data.clinic_b.id,
            auth_id=uuid4(),
            name="Vet fictício B",
            role=Role.VETERINARIAN,
            active=True,
            crmv="9999",
            crmv_state="PI",
        )
        session.add(vet)
        session.flush()
        session.add(
            Appointment(
                clinic_id=data.clinic_b.id,
                patient_id=p,
                veterinarian_id=vet.id,
                starts_at=start,
                ends_at=start + timedelta(hours=1),
                kind="Consulta fictícia B",
            )
        )
        session.add(
            Encounter(
                clinic_id=data.clinic_b.id, patient_id=p, veterinarian_id=vet.id, started_at=start
            )
        )
        session.add(
            Product(
                clinic_id=data.clinic_b.id,
                name="Produto fictício B",
                unit="un",
                minimum_stock=Decimal("1"),
                track_expiry=False,
            )
        )
        session.add(
            Message(
                clinic_id=data.clinic_b.id,
                direction="inbound",
                status="received",
                provider="mock",
                provider_message_id=str(uuid4()),
                phone="+5586999999999",
                body="Privado B",
                needs_attention=True,
            )
        )
    entry(client, token="admin_b", amount_cents=99999)
    result = client.get(
        "/dashboard",
        headers=headers(),
        params={"clinic_id": str(data.clinic_b.id), "role": "admin"},
    ).json()
    assert result["scheduling"]["appointments_total"] == 0
    assert result["scheduling"]["open_encounters"] == 0
    assert result["inventory"]["low_stock_products"] == 0
    assert result["messaging"]["needs_attention"] == 0
    assert result["financial"]["income_cents"] == "0"
    other = dashboard(client, "admin_b")
    assert other["scheduling"]["appointments_total"] == 1
    assert other["inventory"]["low_stock_products"] == 1
    assert other["messaging"]["needs_attention"] == 1
    assert other["financial"]["income_cents"] == "99999"


def test_reading_dashboard_has_no_write_side_effects(
    client: TestClient,
    database: DatabaseFixture,
) -> None:
    for _ in range(2):
        dashboard(client)
    with database.admin.connect() as connection:
        for table in [
            "audit_logs",
            "messages",
            "reminder_jobs",
            "financial_entries",
            "stock_movements",
            "record_entries",
        ]:
            assert connection.scalar(text(f"SELECT count(*) FROM vetsys.{table}")) == 0


def test_database_error_is_generic_without_returning_partial_or_private_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(self: InventoryService, day: date) -> InventoryAlerts:
        raise SQLAlchemyError("PRIVATE-DATABASE-DETAIL")

    monkeypatch.setattr(InventoryService, "alerts", fail)
    response = client.get("/dashboard", headers=headers())
    assert response.status_code == 503
    assert "PRIVATE" not in response.text and "financial" not in response.text


def mocked_service() -> tuple[DashboardService, list[Mock]]:
    scheduling, messaging, inventory, financial = [Mock() for _ in range(4)]
    scheduling.summary.return_value = ScheduleSummary(
        appointments_total=0,
        scheduled=0,
        confirmed=0,
        in_progress=0,
        completed=0,
        cancelled=0,
        no_show=0,
        open_encounters=0,
    )
    messaging.summary.return_value = MessagingSummary(needs_attention=0, simulated=True)
    inventory.alerts.return_value = InventoryAlerts(
        low_stock_products=0, expired_lots=0, expiring_lots=0
    )
    financial.summary.return_value = FinancialSummary(
        income_cents="0", expense_cents="0", difference_cents="0"
    )
    return DashboardService(scheduling, messaging, inventory, financial), [
        scheduling,
        messaging,
        inventory,
        financial,
    ]


@pytest.mark.parametrize("token", ["vet_a", "assistant_a", "inactive_a", "deleted_a"])
def test_service_gates_access_before_querying_financial(data: FixtureData, token: str) -> None:
    service, modules = mocked_service()
    if token in {"inactive_a", "deleted_a"}:
        with pytest.raises(AccessDenied):
            service.read(data.users[token])
        assert not any(module.mock_calls for module in modules)
    else:
        assert service.read(data.users[token]).financial is None
        modules[3].summary.assert_not_called()


@pytest.mark.parametrize(
    "clock,day,start,end",
    [
        ("2026-02-01T01:30:00+00:00", "2026-01-31", "2026-01-01", "2026-01-31"),
        ("2026-02-01T03:00:00+00:00", "2026-02-01", "2026-02-01", "2026-02-28"),
        ("2024-02-29T15:00:00+00:00", "2024-02-29", "2024-02-01", "2024-02-29"),
        ("2027-01-01T01:00:00+00:00", "2026-12-31", "2026-12-01", "2026-12-31"),
    ],
)
def test_summary_calendar_uses_fortaleza_not_utc(
    data: FixtureData,
    monkeypatch: pytest.MonkeyPatch,
    clock: str,
    day: str,
    start: str,
    end: str,
) -> None:
    fixed = datetime.fromisoformat(clock)

    class Clock:
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return fixed.astimezone(tz)

    monkeypatch.setattr("app.modules.dashboard.services.datetime", Clock)
    service, modules = mocked_service()
    result = service.read(data.users["admin_a"])
    assert str(result.day) == day
    assert str(result.month_start) == start and str(result.month_end) == end
    modules[0].summary.assert_called_once_with(date.fromisoformat(day))
    modules[3].summary.assert_called_once_with(
        data.users["admin_a"], date.fromisoformat(start), date.fromisoformat(end)
    )


def test_dashboard_uses_one_snapshot_during_concurrent_financial_write(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready, resume = Event(), Event()
    original = SchedulingService.summary

    def paused(self: SchedulingService, day: date) -> ScheduleSummary:
        result = original(self, day)
        ready.set()
        assert resume.wait(timeout=15)
        return result

    monkeypatch.setattr(SchedulingService, "summary", paused)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(dashboard, client)
        try:
            assert ready.wait(timeout=10)
            entry(client, amount_cents=12345)
        finally:
            resume.set()
        result = pending.result(timeout=15)
    assert result["financial"]["income_cents"] == "0"
    monkeypatch.setattr(SchedulingService, "summary", original)
    assert dashboard(client)["financial"]["income_cents"] == "12345"
