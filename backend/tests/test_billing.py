from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Barrier, Event
from typing import Any
from unittest.mock import Mock
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import set_context
from app.core.errors import AccessDenied, BusinessConflict, InvalidData
from app.core.repositories import ClinicContext
from app.modules.billing.models import FinancialEntry
from app.modules.billing.repositories import FinancialRepository
from app.modules.billing.schemas import EntryCreate, EntryFilters
from app.modules.billing.services import FinancialService
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_registry_api import headers, patient, tutor

ROOT = "/financial/entries"


def day(offset: int = 0) -> str:
    return str(datetime.now(ZoneInfo("America/Fortaleza")).date() + timedelta(days=offset))


def payload(**changes: object) -> dict[str, Any]:
    return (
        dict(
            kind="income",
            description="Consulta fictícia",
            category="Consultas",
            amount_cents=12345,
            occurred_on=day(),
            payment_method="pix",
        )
        | changes
    )


def entry(client: TestClient, token: str = "admin_a", **changes: object) -> dict[str, Any]:
    response = client.post(ROOT, headers=headers(token), json=payload(**changes))
    assert response.status_code == 201, response.text
    return dict(response.json())


def page(client: TestClient, token: str = "admin_a", **filters: object) -> dict[str, Any]:
    response = client.get(
        ROOT, headers=headers(token), params=dict(start=day(-40), end=day()) | filters
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_exact_totals_filters_and_pagination(client: TestClient) -> None:
    entry(client, amount_cents=10, description="Receita % fictícia")
    entry(client, amount_cents=20)
    entry(client, kind="expense", amount_cents=7, category="Insumos", payment_method="cash")
    entry(client, occurred_on=day(-41), amount_cents=999)
    result = page(client, limit=1)
    assert result["total"] == 3 and len(result["items"]) == 1
    assert result["summary"] == {
        "income_cents": "30",
        "expense_cents": "7",
        "difference_cents": "23",
    }
    assert page(client, category="consultas")["total"] == 2
    assert page(client, payment_method="cash")["summary"]["difference_cents"] == "-7"
    assert page(client, q="%")["total"] == 1
    assert page(client, kind="expense")["total"] == 1
    assert page(client, offset=3)["items"] == []
    assert page(client, start=day(-100), end=day(-50))["summary"]["income_cents"] == "0"


def test_reversal_preserves_history_and_corrects_original_period(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    original = entry(client, token="reception_a", occurred_on=day(-35))
    result = client.post(
        f"{ROOT}/{original['id']}/reverse",
        headers=headers(),
        json={"reason": "Correção de digitação"},
    )
    assert result.status_code == 201, result.text
    revised = result.json()
    assert revised["author_name"] == "Fictício reception_a"
    assert revised["status"] == "reversed"
    assert revised["reversal"]["author_id"] == str(data.users["admin_a"].id)
    assert revised["reversal"]["reversal_reason"] == "Correção de digitação"
    assert revised["reversal"]["created_at"][:10] == day()
    assert page(client, start=day(-35), end=day(-35))["summary"]["income_cents"] == "0"
    assert page(client, start=day(), end=day())["total"] == 0
    assert page(client, status="reversed")["total"] == 1
    assert page(client, status="posted")["total"] == 0
    assert (
        client.post(
            f"{ROOT}/{original['id']}/reverse", headers=headers(), json={"reason": "Repetido"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{ROOT}/{revised['reversal']['id']}/reverse",
            headers=headers(),
            json={"reason": "Inválido"},
        ).status_code
        == 404
    )
    with database.admin.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT amount_cents,occurred_on,author_id,reverses_id "
                "FROM vetsys.financial_entries "
                "ORDER BY reverses_id NULLS FIRST"
            )
        ).all()
        assert len(rows) == 2
        assert rows[0].author_id == data.users["reception_a"].id
        assert rows[1].reverses_id == UUID(original["id"])
        assert rows[0].amount_cents == rows[1].amount_cents == 12345
        assert str(rows[0].occurred_on) == str(rows[1].occurred_on) == day(-35)


def test_reception_only_sees_income_and_cannot_reverse_or_create_expenses(
    client: TestClient,
) -> None:
    income = entry(client, token="reception_a")
    expense = entry(client, kind="expense", category="Segredo administrativo")
    result = page(client, token="reception_a")
    assert result["total"] == 1
    assert result["items"][0]["id"] == income["id"]
    assert result["summary"] == {
        "income_cents": "12345",
        "expense_cents": None,
        "difference_cents": None,
    }
    assert "Segredo" not in str(result)
    assert client.get(f"{ROOT}/{expense['id']}", headers=headers("reception_a")).status_code == 404
    assert (
        client.post(ROOT, headers=headers("reception_a"), json=payload(kind="expense")).status_code
        == 403
    )
    assert (
        client.post(
            f"{ROOT}/{income['id']}/reverse",
            headers=headers("reception_a"),
            json={"reason": "Correção"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            ROOT,
            headers=headers("reception_a"),
            params={"start": day(), "end": day(), "kind": "expense"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("token", ["vet_a", "assistant_a", "inactive_a", "deleted_a"])
def test_other_roles_cannot_read_or_write(client: TestClient, token: str) -> None:
    original = entry(client)
    assert (
        client.get(ROOT, headers=headers(token), params={"start": day(), "end": day()}).status_code
        == 403
    )
    assert client.get(f"{ROOT}/{original['id']}", headers=headers(token)).status_code == 403
    assert client.post(ROOT, headers=headers(token), json=payload()).status_code == 403
    assert (
        client.post(
            f"{ROOT}/{original['id']}/reverse", headers=headers(token), json={"reason": "Correção"}
        ).status_code
        == 403
    )


def test_authentication_and_missing_entry(client: TestClient) -> None:
    assert client.get(ROOT, params={"start": day(), "end": day()}).status_code == 401
    assert client.get(f"{ROOT}/{uuid4()}", headers=headers()).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": 0},
        {"amount_cents": -1},
        {"amount_cents": 1.2},
        {"amount_cents": True},
        {"amount_cents": "10"},
        {"amount_cents": 1_000_000_000_001},
        {"occurred_on": day(1)},
        {"occurred_on": "invalid"},
        {"description": " "},
        {"category": " "},
        {"payment_method": "bitcoin"},
        {"kind": "reversal"},
        {"author_name": "Forjado"},
    ],
)
def test_invalid_financial_input(client: TestClient, changes: dict[str, object]) -> None:
    response = client.post(ROOT, headers=headers(), json=payload(**changes))
    assert response.status_code == 422, response.text
    assert page(client)["total"] == 0


@pytest.mark.parametrize("reason", ["", "  ", "ab", "x" * 501, None])
def test_reversal_requires_meaningful_reason(client: TestClient, reason: object) -> None:
    original = entry(client)
    assert (
        client.post(
            f"{ROOT}/{original['id']}/reverse", headers=headers(), json={"reason": reason}
        ).status_code
        == 422
    )
    assert page(client)["summary"]["income_cents"] == "12345"


def test_period_validation_and_maximum_money(client: TestClient) -> None:
    entry(client, amount_cents=1_000_000_000_000)
    entry(client, amount_cents=1_000_000_000_000)
    assert page(client)["summary"]["income_cents"] == "2000000000000"
    assert (
        client.get(ROOT, headers=headers(), params={"start": day(), "end": day(-1)}).status_code
        == 422
    )


def test_optional_links_validated_and_names_preserved(client: TestClient) -> None:
    p, t = patient(client), tutor(client)
    assert (
        client.post(
            ROOT, headers=headers(), json=payload(tutor_id=t["id"], patient_id=p["id"])
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/patients/{p['id']}/tutors",
            headers=headers(),
            json={"tutor_id": t["id"], "is_primary": True},
        ).status_code
        == 200
    )
    original = entry(client, tutor_id=t["id"], patient_id=p["id"])
    assert original["patient_name"] == p["name"] and original["tutor_name"] == t["name"]
    assert (
        client.patch(
            f"/patients/{p['id']}", headers=headers(), json={"name": "Novo nome"}
        ).status_code
        == 200
    )
    assert client.delete(f"/tutors/{t['id']}", headers=headers()).status_code == 204
    assert client.post(ROOT, headers=headers(), json=payload(tutor_id=t["id"])).status_code == 404
    reversed_result = client.post(
        f"{ROOT}/{original['id']}/reverse", headers=headers(), json={"reason": "Correção"}
    )
    assert reversed_result.status_code == 201
    assert reversed_result.json()["patient_name"] == p["name"]


def test_api_and_repository_tenant_isolation(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    original = entry(client)
    entry(client, token="admin_b", amount_cents=111)
    assert page(client, token="admin_b")["summary"]["income_cents"] == "111"
    assert client.get(f"{ROOT}/{original['id']}", headers=headers("admin_b")).status_code == 404
    assert (
        client.post(
            f"{ROOT}/{original['id']}/reverse",
            headers=headers("admin_b"),
            json={"reason": "Correção"},
        ).status_code
        == 404
    )
    other = tutor(client, token="admin_b")
    assert (
        client.post(ROOT, headers=headers(), json=payload(tutor_id=other["id"])).status_code == 404
    )
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        # Mesmo com contexto SQL permissivo para A, repository de B não encontra A.
        repo = FinancialRepository(session, ClinicContext(data.clinic_b.id))
        assert repo.get(UUID(original["id"])) is None


@pytest.mark.parametrize(
    "role,expected", [("admin", 2), ("reception", 1), ("veterinarian", 0), ("assistant", 0)]
)
def test_unfiltered_rls_enforces_roles_and_clinics(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
    role: str,
    expected: int,
) -> None:
    entry(client)
    entry(client, kind="expense")
    entry(client, token="admin_b")
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", role)
        assert len(session.scalars(select(FinancialEntry)).all()) == expected


@pytest.mark.parametrize(
    "kind,token,reversal",
    [
        ("expense", "reception_a", False),
        ("income", "vet_a", False),
        ("income", "assistant_a", False),
        ("income", "reception_a", True),
        ("income", "admin_b", False),
    ],
)
def test_rls_rejects_unauthorized_inserts(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
    kind: str,
    token: str,
    reversal: bool,
) -> None:
    original = entry(client)
    actor = data.users[token]
    with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(actor.clinic_id))
        set_context(session, "vetsys.role", actor.role.value)
        set_context(session, "vetsys.user_id", str(actor.id))
        session.add(
            FinancialEntry(
                clinic_id=data.clinic_a.id,
                **EntryCreate(**payload(kind=kind)).model_dump(),
                author_id=actor.id,
                author_name=actor.name,
                reverses_id=UUID(original["id"]) if reversal else None,
                reversal_reason="Correção" if reversal else None,
            )
        )
        session.flush()


@pytest.mark.parametrize(
    "command",
    [
        "UPDATE vetsys.financial_entries SET amount_cents = 1",
        "DELETE FROM vetsys.financial_entries",
    ],
)
@pytest.mark.parametrize("privileged", [False, True])
def test_immutable_even_through_sql(
    client: TestClient,
    database: DatabaseFixture,
    command: str,
    privileged: bool,
) -> None:
    original = entry(client)
    engine = database.admin if privileged else database.runtime.engine
    with pytest.raises(SQLAlchemyError), engine.begin() as connection:
        connection.execute(text(command))
    assert client.get(f"{ROOT}/{original['id']}", headers=headers()).json()["amount_cents"] == 12345


def test_concurrent_reversals_only_one_is_accepted(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = entry(client)
    barrier = Barrier(2)
    locked = FinancialRepository.locked

    def synchronized(self: FinancialRepository, entry_id: UUID) -> FinancialEntry | None:
        barrier.wait(timeout=10)
        return locked(self, entry_id)

    monkeypatch.setattr(FinancialRepository, "locked", synchronized)

    def reverse() -> int:
        return int(
            client.post(
                f"{ROOT}/{original['id']}/reverse",
                headers=headers(),
                json={"reason": "Correção concorrente"},
            ).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: reverse(), range(2)))
    assert sorted(statuses) == [201, 409]
    assert page(client)["summary"]["income_cents"] == "0"


def test_services_reject_before_accessing_repositories(data: FixtureData) -> None:
    repo, tutors, patients = Mock(), Mock(), Mock()
    service = FinancialService(repo, tutors, patients)
    with pytest.raises(AccessDenied):
        service.create(data.users["reception_a"], EntryCreate(**payload(kind="expense")))
    with pytest.raises(AccessDenied):
        service.reverse(data.users["vet_a"], uuid4(), "Correção")
    with pytest.raises(InvalidData):
        service.reverse(data.users["admin_a"], uuid4(), "  ")
    with pytest.raises(InvalidData):
        service.create(data.users["admin_a"], EntryCreate(**payload(occurred_on=day(1))))
    with pytest.raises(InvalidData):
        service.list(
            data.users["admin_a"],
            EntryFilters(start=date.fromisoformat(day()), end=date.fromisoformat(day(-1))),
            20,
            0,
        )
    assert not repo.mock_calls and not tutors.mock_calls and not patients.mock_calls
    repo.locked.return_value = Mock(reverses_id=None)
    repo.reversals.return_value = {uuid4(): Mock()}
    with pytest.raises(BusinessConflict):
        service.reverse(data.users["admin_a"], uuid4(), "Correção")
    repo.save.assert_not_called()


def test_list_and_totals_share_one_snapshot_during_reversal(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = entry(client)
    ready, resume = Event(), Event()
    list_entries = FinancialRepository.list

    def paused(
        self: FinancialRepository, filters: EntryFilters, limit: int, offset: int
    ) -> tuple[Any, int, int, int]:
        result = list_entries(self, filters, limit, offset)
        ready.set()
        assert resume.wait(timeout=15)
        return result

    monkeypatch.setattr(FinancialRepository, "list", paused)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(page, client)
        try:
            assert ready.wait(timeout=10)
            response = client.post(
                f"{ROOT}/{original['id']}/reverse",
                headers=headers(),
                json={"reason": "Correção durante consulta"},
            )
            assert response.status_code == 201
        finally:
            resume.set()
        snapshot = pending.result(timeout=15)
    assert snapshot["items"][0]["status"] == "posted"
    assert snapshot["summary"]["income_cents"] == "12345"
    monkeypatch.setattr(FinancialRepository, "list", list_entries)
    assert page(client)["items"][0]["status"] == "reversed"
    assert page(client)["summary"]["income_cents"] == "0"


@pytest.mark.parametrize("change", ["amount_cents + 1", "amount_cents"])
def test_database_rejects_mismatched_or_duplicate_reversal(
    client: TestClient,
    database: DatabaseFixture,
    change: str,
) -> None:
    original = entry(client)
    if change == "amount_cents":
        assert (
            client.post(
                f"{ROOT}/{original['id']}/reverse", headers=headers(), json={"reason": "Correção"}
            ).status_code
            == 201
        )
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        # As expressões abaixo são constantes de teste, nunca entrada do usuário.
        connection.execute(
            text(
                "INSERT INTO vetsys.financial_entries "
                "(id,clinic_id,kind,description,category,amount_cents,occurred_on,payment_method,"
                "author_id,author_name,reverses_id,reversal_reason) "
                f"SELECT :new,clinic_id,kind,description,category,{change},"
                "occurred_on,payment_method,"
                "author_id,author_name,id,'Correção' FROM vetsys.financial_entries WHERE id=:id"
            ),
            {"new": uuid4(), "id": UUID(original["id"])},
        )


def test_financial_summary_preserves_totals_above_javascript_safe_integer(
    data: FixtureData,
) -> None:
    repo = Mock()
    repo.list.return_value = ([], 0, 9_007_199_254_740_993, 1)
    repo.reversals.return_value = {}
    service = FinancialService(repo, Mock(), Mock())
    result = service.list(
        data.users["admin_a"],
        EntryFilters(start=date.fromisoformat(day()), end=date.fromisoformat(day())),
        20,
        0,
    )
    assert result.summary.income_cents == "9007199254740993"
    assert result.summary.difference_cents == "9007199254740992"
