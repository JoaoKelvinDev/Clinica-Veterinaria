from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_available_api() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok"}


def test_unknown_route_returns_not_found() -> None:
    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404


def test_health_rejects_writes() -> None:
    with TestClient(app) as client:
        response = client.post("/health", json={"status": "ok"})

    assert response.status_code == 405
