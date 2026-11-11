from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.db import Database
from app.main import create_app


def test_serverless_pooler_uses_tls_and_disables_prepared_statements() -> None:
    with patch("app.core.db.create_engine") as create:
        Database("postgresql+psycopg://example.invalid/postgres", serverless=True)
    create.assert_called_once_with(
        "postgresql+psycopg://example.invalid/postgres",
        pool_pre_ping=True,
        hide_parameters=True,
        pool_size=1,
        max_overflow=0,
        connect_args={"sslmode": "require", "prepare_threshold": None},
    )


def test_local_database_keeps_existing_connection_settings() -> None:
    with patch("app.core.db.create_engine") as create:
        Database("postgresql+psycopg://localhost/postgres")
    create.assert_called_once_with(
        "postgresql+psycopg://localhost/postgres", pool_pre_ping=True, hide_parameters=True
    )


@pytest.mark.parametrize("value,expected", [(None, False), ("0", False), ("1", True)])
def test_serverless_environment_is_explicit(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool
) -> None:
    if value is None:
        monkeypatch.delenv("VERCEL", raising=False)
    else:
        monkeypatch.setenv("VERCEL", value)
    assert Settings.from_environment().serverless is expected


def test_application_passes_serverless_settings_to_database() -> None:
    with patch("app.main.Database") as database:
        app = create_app(
            Settings(database_url="postgresql+psycopg://example.invalid/postgres", serverless=True)
        )
    database.assert_called_once_with(
        "postgresql+psycopg://example.invalid/postgres", serverless=True
    )
    assert app.state.database is database.return_value
