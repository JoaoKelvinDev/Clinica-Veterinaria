from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import set_context
from app.modules.quotes.models import Quote, QuoteItem
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_quotes import budget, decision, payload, present
from tests.test_registry_api import headers


def test_other_clinic_and_assistant_cannot_write(client: TestClient) -> None:
    quote = budget(client)
    assert client.get(f"/quotes/{quote['id']}", headers=headers("admin_b")).status_code == 404
    assert client.get("/quotes", headers=headers("admin_b")).json()["total"] == 0
    assert (
        client.get(f"/quotes/options/{quote['patient_id']}", headers=headers("admin_b")).status_code
        == 404
    )
    assert (
        client.put(
            f"/quotes/{quote['id']}", headers=headers("admin_b"), json=payload(quote)
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/quotes/{quote['id']}", headers=headers("assistant_a"), json=payload(quote)
        ).status_code
        == 403
    )
    for action in ("present", "approve", "reject", "revise"):
        assert (
            client.post(
                f"/quotes/{quote['id']}/{action}",
                headers=headers("assistant_a"),
                json=decision(quote)
                if action in {"approve", "reject"}
                else {"expected_version": 1},
            ).status_code
            == 403
        )


def test_rls_and_presented_header_and_items_are_preserved(
    client: TestClient,
    database: DatabaseFixture,
    data: FixtureData,
) -> None:
    quote = present(client, budget(client))
    quote_id, item_id = UUID(quote["id"]), UUID(quote["items"][0]["id"])
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_b.id))
        set_context(session, "vetsys.role", "admin")
        assert session.scalars(select(Quote)).all() == []
        assert session.scalars(select(QuoteItem)).all() == []
    for sql, identity in (
        (
            "UPDATE vetsys.quotes SET patient_name = 'alterado', version = version + 1 "
            "WHERE id = :id",
            quote_id,
        ),
        ("DELETE FROM vetsys.quotes WHERE id = :id", quote_id),
        ("UPDATE vetsys.quote_items SET quantity = 2 WHERE id = :id", item_id),
        ("DELETE FROM vetsys.quote_items WHERE id = :id", item_id),
    ):
        with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
            connection.execute(text(sql), {"id": identity})
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        set_context(session, "vetsys.user_id", str(data.users["admin_a"].id))
        session.execute(text("DELETE FROM vetsys.quote_items WHERE id = :id"), {"id": item_id})
        assert session.get(QuoteItem, item_id) is not None
    response = client.post(f"/quotes/{quote_id}/approve", headers=headers(), json=decision(quote))
    assert response.status_code == 200
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE vetsys.quotes SET updated_at = now(), version = version + 1 WHERE id = :id"
            ),
            {"id": quote_id},
        )
