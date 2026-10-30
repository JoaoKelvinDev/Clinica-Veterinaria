from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import set_context
from app.core.repositories import ClinicContext
from app.modules.patients.models import Patient, TutorPatient
from app.modules.patients.repositories import LinkRepository, PatientRepository
from app.modules.tutors.models import Tutor
from app.modules.tutors.repositories import TutorRepository
from tests.conftest import DatabaseFixture, FixtureData


@pytest.fixture
def registry(database: DatabaseFixture, data: FixtureData) -> dict[str, UUID]:
    result: dict[str, UUID] = {}
    with Session(database.admin) as session:
        for suffix, clinic in (("a", data.clinic_a), ("b", data.clinic_b)):
            tutor = Tutor(clinic_id=clinic.id, name=f"Tutor fictício {suffix}")
            patient = Patient(clinic_id=clinic.id, name=f"Paciente {suffix}", species="Canina")
            session.add_all([tutor, patient])
            session.flush()
            link = TutorPatient(
                clinic_id=clinic.id, patient_id=patient.id, tutor_id=tutor.id, is_primary=True
            )
            session.add(link)
            session.flush()
            result.update({f"tutor_{suffix}": tutor.id, f"patient_{suffix}": patient.id})
            result[f"link_{suffix}"] = link.id
        session.commit()
    return result


def test_all_registry_repositories_and_unfiltered_queries_are_scoped(
    database: DatabaseFixture, data: FixtureData, registry: dict[str, UUID]
) -> None:
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", "admin")
        context = ClinicContext(data.clinic_a.id)
        assert TutorRepository(session, context).get(registry["tutor_b"]) is None
        assert PatientRepository(session, context).get(registry["patient_b"]) is None
        assert LinkRepository(session, context).get(registry["link_b"]) is None
        assert [row.id for row in session.scalars(select(Tutor))] == [registry["tutor_a"]]
        assert [row.id for row in session.scalars(select(Patient))] == [registry["patient_a"]]
        assert [row.id for row in session.scalars(select(TutorPatient))] == [registry["link_a"]]
        assert LinkRepository(session, context).list(registry["patient_b"]) == []
    with database.runtime.sessions.begin() as session:
        assert list(session.scalars(select(Tutor))) == []
        assert list(session.scalars(select(Patient))) == []
        assert list(session.scalars(select(TutorPatient))) == []


@pytest.mark.parametrize("table", ["tutors", "patients", "tutor_patients"])
def test_database_denies_registry_tenant_reassignment_and_physical_delete(
    database: DatabaseFixture, data: FixtureData, registry: dict[str, UUID], table: str
) -> None:
    key = {"tutors": "tutor_a", "patients": "patient_a", "tutor_patients": "link_a"}[table]
    for sql in (
        f"UPDATE vetsys.{table} SET clinic_id = :clinic WHERE id = :id",
        f"DELETE FROM vetsys.{table} WHERE id = :id",
    ):
        with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
            set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
            set_context(session, "vetsys.role", "admin")
            session.execute(text(sql), {"clinic": data.clinic_b.id, "id": registry[key]})


@pytest.mark.parametrize("role", ["veterinarian", "assistant"])
def test_database_also_restricts_registry_writes_by_role(
    database: DatabaseFixture, data: FixtureData, registry: dict[str, UUID], role: str
) -> None:
    with database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", role)
        for statement, record_id in (
            ("UPDATE vetsys.tutors SET name = 'Tentativa' WHERE id = :id RETURNING id", "tutor_a"),
            (
                "UPDATE vetsys.patients SET name = 'Tentativa' WHERE id = :id RETURNING id",
                "patient_a",
            ),
            (
                "UPDATE vetsys.tutor_patients SET is_primary = false WHERE id = :id RETURNING id",
                "link_a",
            ),
        ):
            assert session.execute(text(statement), {"id": registry[record_id]}).all() == []
    with pytest.raises(SQLAlchemyError), database.runtime.sessions.begin() as session:
        set_context(session, "vetsys.clinic_id", str(data.clinic_a.id))
        set_context(session, "vetsys.role", role)
        session.add(Tutor(clinic_id=data.clinic_a.id, name="Tentativa"))
        session.flush()


def test_composite_foreign_keys_reject_cross_clinic_links_even_for_admin_connection(
    database: DatabaseFixture, data: FixtureData, registry: dict[str, UUID]
) -> None:
    with Session(database.admin) as session, pytest.raises(IntegrityError):
        session.add(
            TutorPatient(
                clinic_id=data.clinic_a.id,
                patient_id=registry["patient_a"],
                tutor_id=registry["tutor_b"],
            )
        )
        session.flush()


def test_database_rejects_two_active_primary_tutors(
    database: DatabaseFixture, data: FixtureData, registry: dict[str, UUID]
) -> None:
    with Session(database.admin) as session, pytest.raises(IntegrityError):
        second = Tutor(clinic_id=data.clinic_a.id, name="Outro tutor fictício")
        session.add(second)
        session.flush()
        session.add(
            TutorPatient(
                clinic_id=data.clinic_a.id,
                patient_id=registry["patient_a"],
                tutor_id=second.id,
                is_primary=True,
            )
        )
        session.flush()
