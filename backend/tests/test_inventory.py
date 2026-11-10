from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import set_context
from app.core.repositories import ClinicContext
from app.modules.inventory.models import Lot, Product, StockMovement
from app.modules.inventory.repositories import LotRepository, MovementRepository, ProductRepository
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_registry_api import headers

ROOT = "/inventory/products"


def today() -> str:
    return str(datetime.now(ZoneInfo("America/Fortaleza")).date())


def expiry(days: int) -> str:
    return str(datetime.now(ZoneInfo("America/Fortaleza")).date() + timedelta(days=days))


def product(client: TestClient, **changes: object) -> dict[str, Any]:
    response = client.post(
        ROOT,
        headers=headers(),
        json={
            "name": "Insumo fictício",
            "unit": "mL",
            "minimum_stock": "2.500",
            "track_expiry": True,
            **changes,
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def post(
    client: TestClient, p: dict[str, Any], action: str, token: str = "admin_a", **values: object
) -> dict[str, Any]:
    response = client.post(
        f"{ROOT}/{p['id']}/{action}",
        headers=headers(token),
        json={"expected_version": p["version"], **values},
    )
    assert response.status_code in {200, 201}, response.text
    return dict(response.json())


def lot(
    client: TestClient, p: dict[str, Any], code: str = "A", days: int = 10, token: str = "admin_a"
) -> dict[str, Any]:
    return post(client, p, "lots", token, code=code, expires_on=expiry(days))


def receive(
    client: TestClient, p: dict[str, Any], index: int, quantity: str, token: str = "admin_a"
) -> dict[str, Any]:
    return post(
        client,
        p,
        "receipts",
        token,
        lot_id=p["lots"][index]["id"],
        quantity=quantity,
        reason="Entrada fictícia",
    )


def history(client: TestClient, p: dict[str, Any]) -> dict[str, Any]:
    return dict(client.get(f"{ROOT}/{p['id']}/movements", headers=headers()).json())


def test_fefo_splits_exact_quantities_and_reuses_lot(client: TestClient) -> None:
    p = lot(client, product(client), "LATER", 20)
    p = receive(client, p, 0, "3.125")
    p = lot(client, p, "EARLY", 5)
    p = receive(client, p, 0, "1.001")
    p = receive(client, p, 0, "0.124")
    p = post(client, p, "issues", quantity="2.125", reason="Consumo fictício")
    assert [item["balance"] for item in p["lots"]] == ["0.000", "2.125"]
    assert p["available_stock"] == "2.125" and p["low_stock"]
    rows = history(client, p)["items"]
    outbound = [row for row in rows if row["kind"] == "outbound"]
    assert len(outbound) == 2
    assert len({row["operation_id"] for row in outbound}) == 1
    assert {row["quantity"] for row in outbound} == {"-1.125", "-1.000"}
    assert all(row["author_name"] == "Fictício admin_a" and row["unit"] == "mL" for row in rows)


def test_expired_stock_adjustments_alerts_and_expiry_day(client: TestClient) -> None:
    p = lot(client, product(client), "EXPIRED", -1)
    expired_id = p["lots"][0]["id"]
    failed = client.post(
        f"{ROOT}/{p['id']}/receipts",
        headers=headers(),
        json={
            "expected_version": p["version"],
            "lot_id": expired_id,
            "quantity": "1",
            "reason": "Entrada inválida",
        },
    )
    assert failed.status_code == 409
    p = post(
        client,
        p,
        "adjustments",
        lot_id=expired_id,
        quantity="3",
        reason="Contagem de estoque vencido",
    )
    p = lot(client, p, "TODAY", 0)
    p = receive(client, p, 1, "2.5")
    assert (p["physical_stock"], p["expired_stock"], p["available_stock"]) == (
        "5.500",
        "3.000",
        "2.500",
    )
    assert not p["low_stock"] and p["expiring_lots"] == 1 and p["expired_lots"] == 1
    # A insuficiência não pode consumir o lote válido parcialmente.
    response = client.post(
        f"{ROOT}/{p['id']}/issues",
        headers=headers(),
        json={
            "expected_version": p["version"],
            "quantity": "3",
            "reason": "Saldo insuficiente",
        },
    )
    assert response.status_code == 409
    assert history(client, p)["total"] == 2
    assert client.get(f"{ROOT}/{p['id']}", headers=headers()).json()["version"] == p["version"]
    p = post(client, p, "issues", quantity="2.5", reason="Uso no dia da validade")
    assert p["available_stock"] == "0.000" and p["physical_stock"] == "3.000"
    p = post(
        client, p, "adjustments", lot_id=expired_id, quantity="-3", reason="Descarte por vencimento"
    )
    assert p["physical_stock"] == "0.000" and p["expired_lots"] == 0


def test_undated_lots_last_and_archive_keeps_history(client: TestClient) -> None:
    p = product(client, track_expiry=False)
    p = post(client, p, "lots", code="UNDATED")
    p = receive(client, p, 0, "1")
    p = lot(client, p, "DATED", 3)
    p = receive(client, p, 0, "2")
    assert (
        client.post(
            f"{ROOT}/{p['id']}/archive", headers=headers(), json={"expected_version": p["version"]}
        ).status_code
        == 409
    )
    p = post(client, p, "issues", quantity="2", reason="Baixa prioriza validade")
    assert p["lots"][0]["balance"] == "0.000" and p["lots"][1]["balance"] == "1.000"
    p = post(client, p, "issues", quantity="1", reason="Baixa restante")
    p = post(client, p, "archive")
    assert p["deleted_at"] is not None
    assert client.get(ROOT, headers=headers()).json()["total"] == 0
    assert client.get(f"{ROOT}?archived=true", headers=headers()).json()["total"] == 1
    assert history(client, p)["total"] == 4
    assert client.get(f"{ROOT}/{p['id']}", headers=headers()).status_code == 200
    assert (
        client.post(
            f"{ROOT}/{p['id']}/lots",
            headers=headers(),
            json={"expected_version": p["version"], "code": "X"},
        ).status_code
        == 404
    )


def test_product_metadata_freeze_snapshot_and_correction_link(client: TestClient) -> None:
    p = receive(client, lot(client, product(client)), 0, "1.234")
    original = history(client, p)["items"][0]
    values = {key: p[key] for key in ("name", "unit", "minimum_stock", "track_expiry")}
    for change in ({"unit": "g"}, {"track_expiry": False}):
        assert (
            client.put(
                f"{ROOT}/{p['id']}",
                headers=headers(),
                json={**values, "expected_version": p["version"], **change},
            ).status_code
            == 409
        )
    response = client.put(
        f"{ROOT}/{p['id']}",
        headers=headers(),
        json={
            **values,
            "expected_version": p["version"],
            "name": "Nome atualizado",
            "minimum_stock": "5",
        },
    )
    assert response.status_code == 200, response.text
    p = response.json()
    p = post(
        client,
        p,
        "adjustments",
        lot_id=p["lots"][0]["id"],
        quantity="-0.234",
        reason="Correção de entrada",
        corrects_id=original["id"],
    )
    rows = history(client, p)["items"]
    assert rows[0]["corrects_id"] == original["id"] and rows[0]["product_name"] == "Nome atualizado"
    assert rows[1]["product_name"] == "Insumo fictício" and p["physical_stock"] == "1.000"
    for quantity, status in (("0", 422), ("-2", 409)):
        assert (
            client.post(
                f"{ROOT}/{p['id']}/adjustments",
                headers=headers(),
                json={
                    "expected_version": p["version"],
                    "lot_id": p["lots"][0]["id"],
                    "quantity": quantity,
                    "reason": "Ajuste inválido",
                },
            ).status_code
            == status
        )


@pytest.mark.parametrize("token", ["admin_a", "vet_a", "assistant_a"])
def test_inventory_operator_roles(client: TestClient, token: str) -> None:
    p = lot(client, product(client), token=token)
    p = receive(client, p, 0, "3", token)
    p = post(client, p, "issues", token, quantity="1", reason="Uso fictício")
    assert p["available_stock"] == "2.000"
    if token != "admin_a":
        assert (
            client.post(
                ROOT,
                headers=headers(token),
                json={"name": "Produto", "unit": "un", "minimum_stock": "0", "track_expiry": False},
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"{ROOT}/{p['id']}/adjustments",
                headers=headers(token),
                json={
                    "expected_version": p["version"],
                    "lot_id": p["lots"][0]["id"],
                    "quantity": "1",
                    "reason": "Inventário fictício",
                },
            ).status_code
            == 403
        )


def test_reception_read_only_and_input_validation(client: TestClient) -> None:
    p = lot(client, product(client))
    for path in (ROOT, f"{ROOT}/{p['id']}", f"{ROOT}/{p['id']}/movements"):
        assert client.get(path, headers=headers("reception_a")).status_code == 200
    for action, values in (
        ("lots", {"code": "B", "expires_on": today()}),
        ("receipts", {"lot_id": p["lots"][0]["id"], "quantity": "1", "reason": "Teste"}),
        ("issues", {"quantity": "1", "reason": "Teste"}),
        ("archive", {}),
    ):
        assert (
            client.post(
                f"{ROOT}/{p['id']}/{action}",
                headers=headers("reception_a"),
                json={"expected_version": p["version"], **values},
            ).status_code
            == 403
        )
    for quantity in (1.234, True, "0", "-1", "1.0001", "NaN", "1000000"):
        assert (
            client.post(
                f"{ROOT}/{p['id']}/issues",
                headers=headers(),
                json={"expected_version": p["version"], "quantity": quantity, "reason": "Teste"},
            ).status_code
            == 422
        )
    assert (
        client.post(
            f"{ROOT}/{p['id']}/lots",
            headers=headers(),
            json={"expected_version": p["version"], "code": "a", "expires_on": today()},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{ROOT}/{p['id']}/lots",
            headers=headers(),
            json={"expected_version": p["version"], "code": "B"},
        ).status_code
        == 422
    )
    assert client.get(ROOT).status_code == 401


def test_inventory_isolation_api_repository_and_rls(
    client: TestClient, database: DatabaseFixture, data: FixtureData
) -> None:
    p = receive(client, lot(client, product(client)), 0, "2")
    for suffix in ("", "/movements"):
        assert (
            client.get(f"{ROOT}/{p['id']}{suffix}", headers=headers("admin_b")).status_code == 404
        )
    assert client.get(ROOT, headers=headers("admin_b")).json()["items"] == []
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_b.id))
        set_context(session, "vetsys.user_id", str(data.users["admin_b"].id))
        set_context(session, "vetsys.role", "admin")
        assert list(session.scalars(select(Product))) == []
        assert list(session.scalars(select(Lot))) == []
        assert list(session.scalars(select(StockMovement))) == []
        # Mesmo um repository construído com contexto errado é contido pelo RLS.
        context = ClinicContext(data.clinic_a.id)
        assert ProductRepository(session, context).get(UUID(p["id"])) is None
        assert LotRepository(session, context).balances([UUID(p["id"])]) == []
        assert MovementRepository(session, context).page(UUID(p["id"]), 20, 0)[1] == 0


@pytest.mark.parametrize(
    "table,assignment", [("stock_movements", "reason = 'Alterado'"), ("lots", "code = 'ALTERADO'")]
)
@pytest.mark.parametrize("delete", [False, True])
def test_immutable_rows_even_for_database_admin(
    client: TestClient, database: DatabaseFixture, table: str, assignment: str, delete: bool
) -> None:
    p = receive(client, lot(client, product(client)), 0, "1")
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        statement = (
            f"DELETE FROM vetsys.{table}" if delete else f"UPDATE vetsys.{table} SET {assignment}"
        )
        connection.execute(text(statement))
    assert history(client, p)["total"] == 1


def test_database_rejects_negative_balance_and_cross_clinic_lot(
    client: TestClient, database: DatabaseFixture, data: FixtureData
) -> None:
    p = receive(client, lot(client, product(client)), 0, "1")
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        connection.execute(
            text("""INSERT INTO vetsys.stock_movements
            (id,clinic_id,product_id,lot_id,operation_id,kind,quantity,reason,author_id,author_name,product_name,unit)
            SELECT gen_random_uuid(),clinic_id,product_id,lot_id,gen_random_uuid(),'outbound',-2,
                'Tentativa negativa',author_id,author_name,product_name,unit
                FROM vetsys.stock_movements LIMIT 1""")
        )
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        connection.execute(
            text("""INSERT INTO vetsys.lots (id,clinic_id,product_id,code,expires_on)
            VALUES (gen_random_uuid(),:clinic,:product,'OTHER',CURRENT_DATE)"""),
            {"clinic": data.clinic_b.id, "product": p["id"]},
        )
    assert client.get(f"{ROOT}/{p['id']}", headers=headers()).json()["physical_stock"] == "1.000"


def test_failed_split_rolls_back_all_movements(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = receive(client, lot(client, product(client), "A", 1), 0, "1")
    p = receive(client, lot(client, p, "B", 2), 1, "1")
    original = MovementRepository.save
    calls = 0

    def fail_second(self: MovementRepository, movement: StockMovement) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("Simulated storage failure")
        original(self, movement)

    monkeypatch.setattr(MovementRepository, "save", fail_second)
    response = client.post(
        f"{ROOT}/{p['id']}/issues",
        headers=headers(),
        json={"expected_version": p["version"], "quantity": "2", "reason": "Baixa fictícia"},
    )
    assert response.status_code == 503
    assert history(client, p)["total"] == 2
    assert client.get(f"{ROOT}/{p['id']}", headers=headers()).json()["available_stock"] == "2.000"


@pytest.mark.parametrize("action", ["issues", "receipts"])
def test_concurrent_same_version_records_one_operation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, action: str
) -> None:
    p = receive(client, lot(client, product(client)), 0, "2")
    barrier, original = Barrier(2), ProductRepository.locked

    def together(self: ProductRepository, product_id: UUID) -> Product | None:
        barrier.wait(timeout=10)
        return original(self, product_id)

    monkeypatch.setattr(ProductRepository, "locked", together)

    def request() -> int:
        values = {
            "expected_version": p["version"],
            "quantity": "1.5",
            "reason": "Operação concorrente",
        }
        if action == "receipts":
            values["lot_id"] = p["lots"][0]["id"]
        return int(
            client.post(f"{ROOT}/{p['id']}/{action}", headers=headers(), json=values).status_code
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request) for _ in range(2)]
        assert sorted(f.result(timeout=20) for f in futures) == [201, 409]
    saved = client.get(f"{ROOT}/{p['id']}", headers=headers()).json()
    assert Decimal(saved["physical_stock"]) == (
        Decimal("0.5") if action == "issues" else Decimal("3.5")
    )
    assert saved["version"] == p["version"] + 1 and history(client, p)["total"] == 2


def test_alert_boundaries_and_expired_physical_stock_prevents_archive(client: TestClient) -> None:
    p = product(client, minimum_stock="0")
    for code, days in (("ZERO", 1), ("THIRTY", 30), ("LATER", 31), ("EXPIRED", -1)):
        p = lot(client, p, code, days)
        current = next(item for item in p["lots"] if item["code"] == code)
        if code != "ZERO":
            p = post(
                client,
                p,
                "adjustments",
                lot_id=current["id"],
                quantity="1",
                reason="Contagem fictícia",
            )
    assert p["expiring_lots"] == 1 and p["expired_lots"] == 1
    assert not p["low_stock"]
    p = post(client, p, "issues", quantity="2", reason="Consumo válido completo")
    assert p["available_stock"] == "0.000" and p["physical_stock"] == "1.000"
    assert (
        client.post(
            f"{ROOT}/{p['id']}/archive", headers=headers(), json={"expected_version": p["version"]}
        ).status_code
        == 409
    )


def test_wrong_lot_correction_and_expanded_lot_code_are_rejected(client: TestClient) -> None:
    p = receive(client, lot(client, product(client)), 0, "1")
    original = history(client, p)["items"][0]
    p = lot(client, p, "B", 20)
    assert (
        client.post(
            f"{ROOT}/{p['id']}/adjustments",
            headers=headers(),
            json={
                "expected_version": p["version"],
                "lot_id": p["lots"][1]["id"],
                "quantity": "1",
                "reason": "Correção inválida",
                "corrects_id": original["id"],
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{ROOT}/{p['id']}/lots",
            headers=headers(),
            json={"expected_version": p["version"], "code": "ß" * 80, "expires_on": today()},
        ).status_code
        == 422
    )
    assert history(client, p)["total"] == 1


@pytest.mark.parametrize("token", ["assistant_a", "reception_a"])
def test_database_rejects_metadata_and_ledger_writes_outside_role(
    client: TestClient, database: DatabaseFixture, data: FixtureData, token: str
) -> None:
    p = receive(client, lot(client, product(client)), 0, "1")
    for statement in (
        "UPDATE vetsys.products SET name = 'Inválido', version = version+1",
        "UPDATE vetsys.stock_movements SET reason = 'Inválido'",
        "DELETE FROM vetsys.stock_movements",
    ):
        expectation = (
            nullcontext()
            if token == "reception_a" and "products" in statement
            else pytest.raises(SQLAlchemyError)
        )
        with expectation, database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.user_id", str(data.users[token].id))
            set_context(session, "vetsys.role", data.users[token].role.value)
            assert session.execute(text(statement + " RETURNING id")).all() == []
    assert history(client, p)["total"] == 1
