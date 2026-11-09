from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import set_context
from app.modules.ai_scribe.models import AiDraft
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_ai_scribe import approval, generate
from tests.test_records import encounter
from tests.test_registry_api import headers


@pytest.mark.parametrize("token", ["admin_a", "assistant_a", "reception_a"])
def test_only_veterinarians_generate_and_resolve(client: TestClient, token: str) -> None:
    opened = encounter(client)
    draft = generate(client, opened["id"])
    assert (
        client.post(
            f"/encounters/{opened['id']}/ai-drafts",
            headers=headers(token),
            json={"transcript": "relato"},
        ).status_code
        == 403
    )
    for action in ("approve", "discard"):
        assert (
            client.post(
                f"/ai-drafts/{draft['id']}/{action}", headers=headers(token), json=approval()
            ).status_code
            == 403
        )
    expected = 403 if token == "reception_a" else 200
    assert client.get(f"/ai-drafts/{draft['id']}", headers=headers(token)).status_code == expected


def test_other_clinic_cannot_read_or_resolve_drafts(
    client: TestClient,
    data: FixtureData,
    database: DatabaseFixture,
) -> None:
    opened = encounter(client)
    draft = generate(client, opened["id"])
    assert (
        client.get(
            f"/patients/{opened['patient_id']}/ai-drafts", headers=headers("admin_b")
        ).status_code
        == 404
    )
    assert client.get(f"/ai-drafts/{draft['id']}", headers=headers("admin_b")).status_code == 404
    # Um veterinário da outra clínica também não pode escrever, mesmo conhecendo o UUID.
    with database.admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE vetsys.users SET role = 'veterinarian', crmv = '9', crmv_state = 'PI' "
                "WHERE id = :id"
            ),
            {"id": data.users["admin_b"].id},
        )
    for action in ("approve", "discard"):
        assert (
            client.post(
                f"/ai-drafts/{draft['id']}/{action}", headers=headers("admin_b"), json=approval()
            ).status_code
            == 404
        )
    assert (
        client.post(
            f"/encounters/{opened['id']}/ai-drafts",
            headers=headers("admin_b"),
            json={"transcript": "relato"},
        ).status_code
        == 404
    )


def test_rls_and_database_preserve_source_and_terminal_state(
    client: TestClient,
    data: FixtureData,
    database: DatabaseFixture,
) -> None:
    draft = generate(client, encounter(client)["id"])
    draft_id = UUID(draft["id"])
    for role, clinic_id, user_id in (
        ("reception", data.clinic_a.id, data.users["reception_a"].id),
        ("veterinarian", data.clinic_b.id, data.users["admin_b"].id),
    ):
        with database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(clinic_id))
            set_context(session, "vetsys.role", role)
            set_context(session, "vetsys.user_id", str(user_id))
            assert session.scalars(select(AiDraft)).all() == []
    for sql in (
        "UPDATE vetsys.ai_drafts SET transcript = 'alterado' WHERE id = :id",
        "DELETE FROM vetsys.ai_drafts WHERE id = :id",
    ):
        with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
            connection.execute(text(sql), {"id": draft_id})
        with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.role", "veterinarian")
            set_context(session, "vetsys.user_id", str(data.users["vet_a"].id))
            session.execute(text(sql), {"id": draft_id})
    assert (
        client.post(f"/ai-drafts/{draft_id}/discard", headers=headers("vet_a")).status_code == 200
    )
    with pytest.raises(SQLAlchemyError), database.admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE vetsys.ai_drafts SET status = 'pending', resolved_by = NULL, "
                "resolved_at = NULL WHERE id = :id"
            ),
            {"id": draft_id},
        )
