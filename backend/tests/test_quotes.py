from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.modules.quotes.models import Quote
from app.modules.quotes.repositories import QuoteRepository
from app.modules.quotes.services import QuoteService
from tests.test_registry_api import headers, patient, tutor


def budget(client: TestClient, *, token: str = "admin_a", **changes: object) -> dict[str, Any]:
    p, t = patient(client), tutor(client)
    assert client.post(
        f"/patients/{p['id']}/tutors", headers=headers(), json={"tutor_id": t["id"]}
    ).status_code in {200, 201}
    values = {
        "patient_id": p["id"],
        "tutor_id": t["id"],
        "items": [
            {
                "kind": "service",
                "description": "Serviço fictício",
                "quantity": "1.5",
                "unit_price_cents": 1250,
            }
        ],
        "discount_cents": 100,
        **changes,
    }
    response = client.post("/quotes", headers=headers(token), json=values)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def payload(quote: dict[str, Any], **changes: object) -> dict[str, Any]:
    return {
        "patient_id": quote["patient_id"],
        "tutor_id": quote["tutor_id"],
        "encounter_id": quote["encounter_id"],
        "valid_until": quote["valid_until"],
        "discount_cents": quote["discount_cents"],
        "expected_version": quote["version"],
        "items": [
            {key: item[key] for key in ("kind", "description", "quantity", "unit_price_cents")}
            for item in quote["items"]
        ],
        **changes,
    }


def present(client: TestClient, quote: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"/quotes/{quote['id']}/present",
        headers=headers(),
        json={"expected_version": quote["version"]},
    )
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def decision(quote: dict[str, Any]) -> dict[str, object]:
    return {"expected_version": quote["version"], "source": "in_person"}


@pytest.mark.parametrize("token", ["admin_a", "vet_a", "reception_a"])
def test_create_exact_budget_and_options(client: TestClient, token: str) -> None:
    quote = budget(client, token=token)
    assert (quote["subtotal_cents"], quote["discount_cents"], quote["total_cents"]) == (
        1875,
        100,
        1775,
    )
    assert quote["status"] == "draft" and quote["items"][0]["line_total_cents"] == 1875
    options = client.get(f"/quotes/options/{quote['patient_id']}", headers=headers(token)).json()
    assert options["tutors"][0]["id"] == quote["tutor_id"]
    assert client.get("/quotes", headers=headers("assistant_a")).json()["total"] == 1


def test_edit_then_present_snapshots_and_revise_approved(client: TestClient) -> None:
    quote = budget(client)
    response = client.put(
        f"/quotes/{quote['id']}", headers=headers(), json=payload(quote, discount_cents=1875)
    )
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["version"] == 2 and edited["total_cents"] == 0
    assert (
        client.put(f"/quotes/{quote['id']}", headers=headers(), json=payload(quote)).status_code
        == 409
    )
    sent = present(client, edited)
    for path, body in (
        (f"/patients/{quote['patient_id']}", {"name": "Paciente renomeado"}),
        (f"/tutors/{quote['tutor_id']}", {"name": "Tutor renomeado"}),
    ):
        assert client.patch(path, headers=headers(), json=body).status_code == 200
    assert (
        client.get(f"/quotes/{quote['id']}", headers=headers()).json()["patient_name"]
        == sent["patient_name"]
    )
    approved = client.post(
        f"/quotes/{quote['id']}/approve", headers=headers("reception_a"), json=decision(sent)
    )
    assert approved.status_code == 200, approved.text
    assert (
        approved.json()["status"] == "approved"
        and approved.json()["decision_source"] == "in_person"
    )
    assert (
        client.put(
            f"/quotes/{quote['id']}", headers=headers(), json=payload(approved.json())
        ).status_code
        == 409
    )
    revised = client.post(
        f"/quotes/{quote['id']}/revise",
        headers=headers("vet_a"),
        json={"expected_version": approved.json()["version"]},
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["source_quote_id"] == quote["id"] and revised.json()["status"] == "draft"
    assert revised.json()["patient_name"] == "Paciente renomeado"
    assert client.get(f"/quotes/{quote['id']}", headers=headers()).json() == approved.json()


def test_rejection_and_expiry_block_approval(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    quote = present(client, budget(client, valid_until=str(date.today())))
    future = date.today() + timedelta(days=1)
    monkeypatch.setattr(QuoteService, "today", lambda self: future)
    assert client.get(f"/quotes/{quote['id']}", headers=headers()).json()["status"] == "expired"
    assert client.get("/quotes?status=expired", headers=headers()).json()["total"] == 1
    assert client.get("/quotes?status=sent", headers=headers()).json()["total"] == 0
    assert (
        client.post(
            f"/quotes/{quote['id']}/approve", headers=headers(), json=decision(quote)
        ).status_code
        == 409
    )
    revised = client.post(
        f"/quotes/{quote['id']}/revise",
        headers=headers(),
        json={"expected_version": quote["version"]},
    )
    assert revised.status_code == 201 and revised.json()["valid_until"] is None


def test_record_rejection_and_require_other_source_note(client: TestClient) -> None:
    quote = present(client, budget(client))
    assert (
        client.post(
            f"/quotes/{quote['id']}/reject",
            headers=headers(),
            json={"expected_version": quote["version"], "source": "other"},
        ).status_code
        == 422
    )
    response = client.post(
        f"/quotes/{quote['id']}/reject",
        headers=headers(),
        json={
            "expected_version": quote["version"],
            "source": "other",
            "note": "Comunicação fictícia no balcão",
        },
    )
    assert response.status_code == 200 and response.json()["status"] == "rejected"


def test_invalid_links_dates_and_client_total_are_rejected(client: TestClient) -> None:
    quote = budget(client)
    invalid_changes: list[dict[str, object]] = [
        {"discount_cents": 1876},
        {"total_cents": 1},
        {"items": []},
        {"valid_until": str(date.today() - timedelta(days=1))},
        {"tutor_id": tutor(client)["id"]},
    ]
    for changes in invalid_changes:
        values = payload(quote, **changes)
        values.pop("expected_version")
        assert client.post("/quotes", headers=headers(), json=values).status_code == 422
    other = patient(client)
    encounter = client.post(
        "/encounters", headers=headers("vet_a"), json={"patient_id": other["id"]}
    ).json()
    assert (
        client.put(
            f"/quotes/{quote['id']}",
            headers=headers(),
            json=payload(quote, encounter_id=encounter["id"]),
        ).status_code
        == 422
    )
    assert client.get(f"/quotes/{quote['id']}", headers=headers()).json()["version"] == 1


@pytest.mark.parametrize("second_action", ["approve", "reject"])
def test_concurrent_decisions_allow_one_transition(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, second_action: str
) -> None:
    quote = present(client, budget(client))
    barrier, original = Barrier(2), QuoteRepository.locked

    def together(self: QuoteRepository, quote_id: UUID) -> Quote | None:
        barrier.wait(timeout=10)
        return original(self, quote_id)

    monkeypatch.setattr(QuoteRepository, "locked", together)

    def request(action: str) -> int:
        response = client.post(
            f"/quotes/{quote['id']}/{action}", headers=headers(), json=decision(quote)
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request, action) for action in ("approve", second_action)]
        statuses = [future.result(timeout=20) for future in futures]
    assert sorted(statuses) == [200, 409], statuses


def test_concurrent_edit_and_presentation_preserve_winning_version(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quote = budget(client)
    barrier, original = Barrier(2), QuoteRepository.locked

    def together(self: QuoteRepository, quote_id: UUID) -> Quote | None:
        barrier.wait(timeout=10)
        return original(self, quote_id)

    monkeypatch.setattr(QuoteRepository, "locked", together)

    def request(edit: bool) -> int:
        response = (
            client.put(
                f"/quotes/{quote['id']}", headers=headers(), json=payload(quote, discount_cents=0)
            )
            if edit
            else client.post(
                f"/quotes/{quote['id']}/present", headers=headers(), json={"expected_version": 1}
            )
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(request, edit) for edit in (True, False)]
        statuses = [future.result(timeout=20) for future in futures]
    assert sorted(statuses) == [200, 409], statuses
    saved = client.get(f"/quotes/{quote['id']}", headers=headers()).json()
    assert saved["version"] == 2
    assert (saved["status"], saved["discount_cents"]) in {("draft", 0), ("sent", 100)}
