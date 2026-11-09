from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailable
from app.modules.ai_scribe.models import AiDraft
from app.modules.ai_scribe.repositories import DraftRepository
from app.modules.records.models import AuditLog, RecordEntry
from app.providers.llm import MockLLMProvider
from tests.conftest import DatabaseFixture, FixtureData
from tests.test_records import ENTRY, encounter
from tests.test_registry_api import headers


def generate(client: TestClient, encounter_id: object, **values: object) -> dict[str, Any]:
    response = client.post(
        f"/encounters/{encounter_id}/ai-drafts",
        headers=headers("vet_a"),
        json=values or {"source": "text", "transcript": "Relato do responsável: Relato fictício"},
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def approval(**values: object) -> dict[str, object]:
    return {"review_confirmed": True, "record": {**ENTRY, **values}}


def test_invalid_provider_response_is_rejected_without_persistence(
    client: TestClient,
    database: DatabaseFixture,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    opened = encounter(client)
    monkeypatch.setattr(
        MockLLMProvider,
        "generate",
        lambda *args, **kwargs: {
            "complaint": 42,
            "uncertainties": ["conteúdo fictício privado"],
        },
    )
    response = client.post(
        f"/encounters/{opened['id']}/ai-drafts",
        headers=headers("vet_a"),
        json={"transcript": "conteúdo fictício privado"},
    )
    assert response.status_code == 503
    assert "conteúdo fictício privado" not in response.text + caplog.text
    with Session(database.admin) as session:
        assert session.scalars(select(AiDraft)).all() == []
        assert session.scalars(select(RecordEntry)).all() == []


def test_generation_remains_separate_and_tracks_source_and_model(
    client: TestClient,
    data: FixtureData,
    database: DatabaseFixture,
) -> None:
    opened = encounter(client)
    draft = generate(client, opened["id"], source="mock_audio", sample_id="consultation")
    assert draft["status"] == "pending" and draft["record_entry_id"] is None
    assert draft["simulated"] is True
    assert draft["requested_by"] == str(data.users["vet_a"].id)
    assert draft["llm_model"] == "mock-llm-v1" and draft["stt_model"] == "mock-stt-v1"
    assert draft["prompt_version"] == "scribe-pt-br-v1"
    assert draft["content"]["presumptive_diagnosis"] is None
    with Session(database.admin) as session:
        assert session.scalars(select(RecordEntry)).all() == []
    listing = client.get(f"/patients/{opened['patient_id']}/ai-drafts", headers=headers()).json()
    assert [item["id"] for item in listing] == [draft["id"]]
    assert (
        client.get(f"/ai-drafts/{draft['id']}", headers=headers("assistant_a")).status_code == 200
    )


def test_approval_uses_reviewed_values_author_crmv_audit_and_return_planning(
    client: TestClient,
    data: FixtureData,
    database: DatabaseFixture,
) -> None:
    opened = encounter(client)
    draft = generate(client, opened["id"])
    follow_up = str(date.today() + timedelta(days=10))
    result = client.post(
        f"/ai-drafts/{draft['id']}/approve",
        headers=headers("vet_a"),
        json=approval(complaint="Relato revisado pelo veterinário", follow_up_on=follow_up),
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["status"] == "approved" and body["resolved_by"] == str(data.users["vet_a"].id)
    assert body["content"] == draft["content"] and body["transcript"] == draft["transcript"]
    record = client.get(f"/patients/{opened['patient_id']}/record", headers=headers()).json()
    saved = record["entries"][0]
    assert saved["id"] == body["record_entry_id"]
    assert saved["complaint"] == "Relato revisado pelo veterinário"
    assert saved["author_id"] == str(data.users["vet_a"].id)
    assert saved["author_crmv"] == "CRMV-PI 1234" and saved["version"] == 1
    assert saved["encounter_id"] == str(opened["id"])
    messages = client.get("/messaging", headers=headers()).json()
    assert any(job["kind"] == "follow_up" for job in messages["upcoming"])
    with Session(database.admin) as session:
        entities = list(session.scalars(select(AuditLog.entity)))
        assert (
            "ai_draft" in entities
            and "ai_draft_approval" in entities
            and "record_entry" in entities
        )
    for action in ("approve", "discard"):
        response = client.post(
            f"/ai-drafts/{draft['id']}/{action}", headers=headers("vet_a"), json=approval()
        )
        assert response.status_code == 409


def test_approving_veterinarian_is_author_even_when_another_requested(
    client: TestClient,
    data: FixtureData,
    database: DatabaseFixture,
) -> None:
    draft = generate(client, encounter(client)["id"])
    reviewer_id = data.users["assistant_a"].id
    with database.admin.begin() as connection:
        connection.execute(
            text(
                "UPDATE vetsys.users SET role = 'veterinarian', crmv = '9999', "
                "crmv_state = 'PI' WHERE id = :id"
            ),
            {"id": reviewer_id},
        )
    response = client.post(
        f"/ai-drafts/{draft['id']}/approve", headers=headers("assistant_a"), json=approval()
    )
    assert response.status_code == 200, response.text
    assert response.json()["requested_by"] == str(data.users["vet_a"].id)
    assert response.json()["resolved_by"] == str(reviewer_id)
    with Session(database.admin) as session:
        entry = session.get(RecordEntry, UUID(response.json()["record_entry_id"]))
        assert entry is not None
        assert entry.author_id == reviewer_id and entry.author_crmv == "CRMV-PI 9999"


def test_failure_linking_approval_rolls_back_official_record_and_reminders(
    client: TestClient,
    database: DatabaseFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft = generate(client, encounter(client)["id"])
    original = DraftRepository.save

    def fail_resolution(self: DraftRepository, item: AiDraft) -> None:
        if item.status == "approved":
            raise ServiceUnavailable("MOCK: falha ao vincular aprovação")
        original(self, item)

    monkeypatch.setattr(DraftRepository, "save", fail_resolution)
    response = client.post(
        f"/ai-drafts/{draft['id']}/approve",
        headers=headers("vet_a"),
        json=approval(follow_up_on=str(date.today() + timedelta(days=10))),
    )
    assert response.status_code == 503
    with Session(database.admin) as session:
        assert session.scalars(select(RecordEntry)).all() == []
        stored = session.get(AiDraft, UUID(draft["id"]))
        assert stored is not None and stored.status == "pending"
    assert client.get("/messaging", headers=headers()).json()["upcoming"] == []


@pytest.mark.parametrize("review", [None, False, "true", 1])
def test_explicit_review_is_required(
    client: TestClient, database: DatabaseFixture, review: object
) -> None:
    draft = generate(client, encounter(client)["id"])
    values = {"record": ENTRY, **({"review_confirmed": review} if review is not None else {})}
    response = client.post(
        f"/ai-drafts/{draft['id']}/approve", headers=headers("vet_a"), json=values
    )
    assert response.status_code == 422
    with Session(database.admin) as session:
        assert session.scalars(select(RecordEntry)).all() == []
        stored = session.get(AiDraft, UUID(draft["id"]))
        assert stored is not None and stored.status == "pending"


def test_invalid_review_does_not_resolve_or_create_partial_record(client: TestClient) -> None:
    draft = generate(client, encounter(client)["id"])
    response = client.post(
        f"/ai-drafts/{draft['id']}/approve",
        headers=headers("vet_a"),
        json={"review_confirmed": True, "record": {"complaint": "Revisado"}},
    )
    assert response.status_code == 422
    invalid_date = client.post(
        f"/ai-drafts/{draft['id']}/approve",
        headers=headers("vet_a"),
        json=approval(follow_up_on=str(date.today() - timedelta(days=1))),
    )
    assert invalid_date.status_code == 422
    assert client.get(f"/ai-drafts/{draft['id']}", headers=headers()).json()["status"] == "pending"


def test_discard_preserves_original_and_never_creates_entry(
    client: TestClient,
    database: DatabaseFixture,
) -> None:
    draft = generate(client, encounter(client)["id"])
    result = client.post(f"/ai-drafts/{draft['id']}/discard", headers=headers("vet_a"))
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "discarded" and result.json()["content"] == draft["content"]
    with Session(database.admin) as session:
        assert session.scalars(select(RecordEntry)).all() == []
    assert (
        client.post(
            f"/ai-drafts/{draft['id']}/approve", headers=headers("vet_a"), json=approval()
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"transcript": " "},
        {"transcript": "x" * 20001},
        {"source": "mock_audio", "sample_id": "real.wav"},
        {"source": "mock_audio", "sample_id": "consultation", "transcript": "texto"},
        {"transcript": "relato", "unexpected": "x"},
    ],
)
def test_invalid_generation_input_is_rejected(
    client: TestClient, values: dict[str, object]
) -> None:
    opened = encounter(client)
    assert (
        client.post(
            f"/encounters/{opened['id']}/ai-drafts", headers=headers("vet_a"), json=values
        ).status_code
        == 422
    )


@pytest.mark.parametrize("last_action", ["approve", "discard"])
def test_concurrent_resolution_creates_at_most_one_record(
    client: TestClient,
    database: DatabaseFixture,
    monkeypatch: pytest.MonkeyPatch,
    last_action: str,
) -> None:
    draft = generate(client, encounter(client)["id"])
    barrier = Barrier(2)
    original = DraftRepository.locked

    def together(self: DraftRepository, draft_id: UUID) -> AiDraft | None:
        barrier.wait(timeout=10)
        return original(self, draft_id)

    monkeypatch.setattr(DraftRepository, "locked", together)

    def resolve(action: str) -> int:
        response = client.post(
            f"/ai-drafts/{draft['id']}/{action}", headers=headers("vet_a"), json=approval()
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(resolve, action) for action in ("approve", last_action)]
        statuses = [future.result(timeout=20) for future in futures]
    assert sorted(statuses) == [200, 409], statuses
    with Session(database.admin) as session:
        stored = session.get(AiDraft, UUID(draft["id"]))
        assert stored is not None
        entries = list(session.scalars(select(RecordEntry)))
        assert len(entries) == (1 if stored.status == "approved" else 0)
