import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import set_context, verify_runtime_role
from app.core.errors import ServiceUnavailable
from app.core.repositories import ClinicContext
from app.modules.clinics.models import User
from app.modules.clinics.repositories import ClinicRepository, UserRepository
from tests.conftest import DatabaseFixture, FixtureData


def test_repository_scope_and_rls(database: DatabaseFixture, data: FixtureData) -> None:
    with database.runtime.sessions.begin() as session:
        verify_runtime_role(session)
        set_context(session, "vetsys.auth_id", str(data.users["admin_a"].auth_id))
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        context = ClinicContext(data.clinic_a.id)
        assert UserRepository(session, context).get(data.users["admin_b"].id) is None
        assert ClinicRepository(session, context).get(data.clinic_b.id) is None
        # Consulta sem filtro proposital: o próprio banco ainda isola a clínica.
        assert all(user.clinic_id == data.clinic_a.id for user in session.scalars(select(User)))
        rows = session.execute(
            text("UPDATE vetsys.users SET name = 'Tentativa' WHERE id = :id RETURNING id"),
            {"id": data.users["admin_b"].id},
        ).all()
        assert rows == []
    # O pool não pode preservar contexto da requisição anterior.
    with database.runtime.sessions.begin() as session:
        assert list(session.scalars(select(User))) == []


def test_identity_resolution_only_exposes_current_user(
    database: DatabaseFixture, data: FixtureData
) -> None:
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.auth_id", str(data.users["admin_a"].auth_id))
        visible = list(session.scalars(select(User)))
        assert [user.id for user in visible] == [data.users["admin_a"].id]


def test_runtime_cannot_reassign_tenant(database: DatabaseFixture, data: FixtureData) -> None:
    with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        session.execute(
            text("UPDATE vetsys.users SET clinic_id = :clinic WHERE id = :id"),
            {"clinic": data.clinic_b.id, "id": data.users["admin_a"].id},
        )


def test_administrative_connection_is_rejected(database: DatabaseFixture) -> None:
    from sqlalchemy.orm import Session

    with Session(database.admin) as session, pytest.raises(ServiceUnavailable):
        verify_runtime_role(session)
