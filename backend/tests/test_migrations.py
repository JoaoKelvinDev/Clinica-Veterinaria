import os
from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.engine import make_url


def test_migration_can_upgrade_downgrade_and_upgrade() -> None:
    source = make_url(os.environ["MIGRATION_DATABASE_URL"])
    assert source.host in {"127.0.0.1", "localhost", "host.docker.internal"}
    name = f"vetsys_migration_test_{uuid4().hex}"
    admin_dsn = source.set(drivername="postgresql").render_as_string(hide_password=False)
    test_url = source.set(database=name).render_as_string(hide_password=False)
    original = os.environ["MIGRATION_DATABASE_URL"]
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        os.environ["MIGRATION_DATABASE_URL"] = test_url
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        dsn = source.set(database=name, drivername="postgresql").render_as_string(
            hide_password=False
        )
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT has_column_privilege('vetsys_app', 'vetsys.reminder_jobs', "
                "'due_at', 'UPDATE')"
            ).fetchone() == (True,)
            assert connection.execute(
                "SELECT has_column_privilege('vetsys_app', 'vetsys.reminder_jobs', "
                "'clinic_id', 'UPDATE')"
            ).fetchone() == (False,)
        command.downgrade(config, "d4a81f6c9e27")
        with psycopg.connect(dsn) as connection:
            assert connection.execute(
                "SELECT has_column_privilege('vetsys_app', 'vetsys.reminder_jobs', "
                "'due_at', 'UPDATE')"
            ).fetchone() == (False,)
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        dsn = source.set(database=name, drivername="postgresql").render_as_string(
            hide_password=False
        )
        with psycopg.connect(dsn) as connection:
            rows = connection.execute(
                "SELECT tablename, rowsecurity FROM pg_tables "
                "WHERE schemaname = 'vetsys' AND tablename <> 'alembic_version'"
            ).fetchall()
            assert sorted(rows) == [
                (name, True)
                for name in (
                    "ai_drafts",
                    "appointments",
                    "audit_logs",
                    "clinics",
                    "encounters",
                    "messages",
                    "patient_documents",
                    "patients",
                    "record_entries",
                    "reminder_jobs",
                    "tutor_patients",
                    "tutors",
                    "users",
                    "vaccine_records",
                    "weight_records",
                )
            ]
            policies = connection.execute(
                "SELECT qual, with_check FROM pg_policies WHERE schemaname = 'vetsys'"
            ).fetchall()
            assert len(policies) == 38
            assert all("SELECT" in (qual or check) for qual, check in policies)
    finally:
        os.environ["MIGRATION_DATABASE_URL"] = original
        with psycopg.connect(admin_dsn, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
