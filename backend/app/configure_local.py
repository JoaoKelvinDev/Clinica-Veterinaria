"""Migra e configura somente a instância local autorizada."""

import os
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql


def main() -> None:
    url = os.environ["MIGRATION_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    if urlparse(url).hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("A configuração automática é exclusiva do banco local.")
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    with psycopg.connect(url) as connection:
        flags = connection.execute(
            "SELECT rolsuper, rolbypassrls, rolinherit FROM pg_roles WHERE rolname = 'vetsys_app'"
        ).fetchone()
        if flags != (False, False, False):
            raise RuntimeError("O papel vetsys_app precisa ser restrito e não herdar privilégios.")
        connection.execute(
            sql.SQL("ALTER ROLE vetsys_app LOGIN PASSWORD {}").format(
                sql.Literal(os.environ["LOCAL_APP_PASSWORD"])
            )
        )
        # O banco de testes é separado da aplicação e não contém dados reais.
    with psycopg.connect(url, autocommit=True) as connection:
        if (
            connection.execute("SELECT 1 FROM pg_database WHERE datname = 'vetsys_test'").fetchone()
            is None
        ):
            connection.execute("CREATE DATABASE vetsys_test")


if __name__ == "__main__":
    main()
