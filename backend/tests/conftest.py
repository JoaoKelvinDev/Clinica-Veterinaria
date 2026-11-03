import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import Database
from app.core.errors import AuthenticationRequired
from app.main import create_app
from app.modules.clinics.models import Clinic, Role, User
from app.providers.storage import MemoryFileStorage


@dataclass
class DatabaseFixture:
    admin: Engine
    runtime: Database


@pytest.fixture(scope="session")
def database() -> Iterator[DatabaseFixture]:
    admin_url = os.getenv("MIGRATION_DATABASE_URL", "")
    runtime_url = os.getenv("DATABASE_URL", "")
    if not admin_url or not runtime_url:
        pytest.fail("Execute npm run setup e use uv run --env-file ../.env --frozen pytest")
    admin = make_url(admin_url).set(database="vetsys_test")
    runtime = make_url(runtime_url).set(database="vetsys_test")
    if admin.host not in {"127.0.0.1", "localhost", "host.docker.internal"}:
        pytest.fail("Os testes de integração aceitam somente banco local isolado")
    previous = os.environ.get("MIGRATION_DATABASE_URL")
    os.environ["MIGRATION_DATABASE_URL"] = admin.render_as_string(hide_password=False)
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous is None:
            os.environ.pop("MIGRATION_DATABASE_URL", None)
        else:
            os.environ["MIGRATION_DATABASE_URL"] = previous
    db = DatabaseFixture(
        create_engine(admin, hide_parameters=True),
        Database(runtime.render_as_string(hide_password=False)),
    )
    yield db
    db.admin.dispose()
    db.runtime.engine.dispose()


@dataclass
class FixtureData:
    clinic_a: Clinic
    clinic_b: Clinic
    users: dict[str, User]


@pytest.fixture
def data(database: DatabaseFixture) -> FixtureData:
    with database.admin.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE vetsys.messages, vetsys.reminder_jobs, vetsys.patient_documents, "
                "vetsys.audit_logs, vetsys.vaccine_records, "
                "vetsys.weight_records, "
                "vetsys.record_entries, vetsys.encounters, vetsys.appointments, "
                "vetsys.tutor_patients, vetsys.patients, vetsys.tutors, "
                "vetsys.users, vetsys.clinics"
            )
        )
    with Session(database.admin, expire_on_commit=False) as session:
        a, b = uuid4(), uuid4()
        clinic_a = Clinic(id=a, clinic_id=a, name="Clínica fictícia A")
        clinic_b = Clinic(id=b, clinic_id=b, name="Clínica fictícia B")
        session.add_all([clinic_a, clinic_b])
        session.flush()
        users: dict[str, User] = {}
        for key, clinic, role in (
            ("admin_a", a, Role.ADMIN),
            ("admin_b", b, Role.ADMIN),
            ("vet_a", a, Role.VETERINARIAN),
            ("assistant_a", a, Role.ASSISTANT),
            ("reception_a", a, Role.RECEPTION),
            ("inactive_a", a, Role.RECEPTION),
            ("deleted_a", a, Role.RECEPTION),
        ):
            user = User(
                id=uuid4(),
                clinic_id=clinic,
                auth_id=uuid4(),
                name=f"Fictício {key}",
                role=role,
                active=key != "inactive_a",
                crmv="1234" if role == Role.VETERINARIAN else None,
                crmv_state="PI" if role == Role.VETERINARIAN else None,
                deleted_at=datetime.now(UTC) if key == "deleted_a" else None,
            )
            users[key] = user
            session.add(user)
        session.commit()
        return FixtureData(clinic_a, clinic_b, users)


class MockAuthProvider:
    def __init__(self, identities: dict[str, UUID]) -> None:
        self.identities = identities

    def verify(self, token: str) -> UUID:
        logging.getLogger(__name__).info("MOCK authentication provider")
        if token not in self.identities:
            raise AuthenticationRequired("Sessão inválida ou expirada.")
        return self.identities[token]


@pytest.fixture
def client(database: DatabaseFixture, data: FixtureData) -> Iterator[TestClient]:
    provider = MockAuthProvider(
        {**{key: user.auth_id for key, user in data.users.items()}, "unassigned": uuid4()}
    )
    application = create_app(
        Settings(),
        database=database.runtime,
        auth_provider=provider,
        file_storage=MemoryFileStorage(),
    )
    with TestClient(application) as test_client:
        yield test_client
