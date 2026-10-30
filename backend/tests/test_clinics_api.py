import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.clinics.models import Clinic, User
from tests.conftest import DatabaseFixture, FixtureData


def headers(token: str = "admin_a") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("token", [None, "invalid", "expired"])
def test_authentication_is_required(client: TestClient, token: str | None) -> None:
    response = client.get("/me", headers=headers(token) if token else {})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["inactive_a", "deleted_a", "unassigned"])
def test_inactive_and_deleted_users_are_blocked(client: TestClient, token: str) -> None:
    assert client.get("/me", headers=headers(token)).status_code == 403


def test_profile_and_list_are_isolated(client: TestClient, data: FixtureData) -> None:
    profile = client.get("/me", headers=headers()).json()
    assert profile["clinic"]["id"] == str(data.clinic_a.id)
    assert "auth_id" not in profile["user"]
    users = client.get("/users", headers=headers()).json()
    assert all(user["clinic_id"] == str(data.clinic_a.id) for user in users)
    assert str(data.users["deleted_a"].id) not in {user["id"] for user in users}


def test_other_clinic_cannot_be_read_or_changed(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    target = data.users["admin_b"]
    assert client.get(f"/users/{target.id}", headers=headers()).status_code == 404
    assert (
        client.patch(
            f"/users/{target.id}", headers=headers(), json={"name": "Tentativa"}
        ).status_code
        == 404
    )
    with Session(database.admin) as session:
        actual = session.get(User, target.id)
        assert actual is not None and actual.name == target.name


@pytest.mark.parametrize("token", ["vet_a", "assistant_a", "reception_a"])
def test_non_admin_cannot_manage_users_or_clinic(
    client: TestClient, data: FixtureData, token: str
) -> None:
    assert client.get("/me", headers=headers(token)).status_code == 200
    assert client.get("/users", headers=headers(token)).status_code == 403
    assert (
        client.patch("/clinic", headers=headers(token), json={"name": "Tentativa"}).status_code
        == 403
    )
    assert (
        client.patch(
            f"/users/{data.users[token].id}", headers=headers(token), json={"role": "admin"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "changes",
    [{"clinic_id": "ignored"}, {"auth_id": "ignored"}, {"role": None}, {"name": "   "}, {}],
)
def test_invalid_or_immutable_fields_are_rejected(
    client: TestClient, data: FixtureData, changes: dict[str, object]
) -> None:
    response = client.patch(
        f"/users/{data.users['reception_a'].id}", headers=headers(), json=changes
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_data"


def test_user_deactivation_takes_effect_for_existing_session(
    client: TestClient, data: FixtureData
) -> None:
    target = data.users["reception_a"]
    assert client.get("/me", headers=headers("reception_a")).status_code == 200
    assert (
        client.patch(f"/users/{target.id}", headers=headers(), json={"active": False}).status_code
        == 200
    )
    assert client.get("/me", headers=headers("reception_a")).status_code == 403


def test_last_admin_cannot_be_deactivated(client: TestClient, data: FixtureData) -> None:
    response = client.patch(
        f"/users/{data.users['admin_a'].id}", headers=headers(), json={"active": False}
    )
    assert response.status_code == 409


def test_veterinarian_requires_crmv(client: TestClient, data: FixtureData) -> None:
    target = data.users["assistant_a"].id
    assert (
        client.patch(
            f"/users/{target}", headers=headers(), json={"role": "veterinarian"}
        ).status_code
        == 422
    )
    response = client.patch(
        f"/users/{target}",
        headers=headers(),
        json={"role": "veterinarian", "crmv": "4321", "crmv_state": "pi"},
    )
    assert response.status_code == 200
    assert response.json()["crmv_state"] == "PI"


def test_clinic_rename_does_not_change_other_clinic(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    response = client.patch("/clinic", headers=headers(), json={"name": "Novo nome fictício"})
    assert response.status_code == 200
    with Session(database.admin) as session:
        other = session.scalar(select(Clinic).where(Clinic.id == data.clinic_b.id))
        assert other is not None and other.name == data.clinic_b.name


def test_client_cannot_choose_another_clinic(client: TestClient, data: FixtureData) -> None:
    response = client.get("/me", headers={**headers(), "X-Clinic-Id": str(data.clinic_b.id)})
    assert response.status_code == 200
    assert response.json()["clinic"]["id"] == str(data.clinic_a.id)


def test_changed_role_takes_effect_without_new_login(client: TestClient, data: FixtureData) -> None:
    promoted = client.patch(
        f"/users/{data.users['assistant_a'].id}", headers=headers(), json={"role": "admin"}
    )
    assert promoted.status_code == 200
    demoted = client.patch(
        f"/users/{data.users['admin_a'].id}", headers=headers(), json={"role": "assistant"}
    )
    assert demoted.status_code == 200
    assert client.get("/users", headers=headers()).status_code == 403


def test_deleted_clinic_is_blocked(
    client: TestClient, data: FixtureData, database: DatabaseFixture
) -> None:
    from datetime import UTC, datetime

    with Session(database.admin) as session:
        clinic = session.get(Clinic, data.clinic_a.id)
        assert clinic is not None
        clinic.deleted_at = datetime.now(UTC)
        session.commit()
    assert client.get("/me", headers=headers()).status_code == 403
