from datetime import date
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class Patient(TenantModel):
    __tablename__ = "patients"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_patient_clinic_id"),
        CheckConstraint("sex IN ('male', 'female', 'unknown')", name="patient_sex"),
        CheckConstraint(
            "birth_date IS NULL OR estimated_age_months IS NULL", name="one_age_source"
        ),
        CheckConstraint("estimated_age_months >= 0", name="non_negative_age"),
        Index(
            "uq_patient_active_microchip",
            "clinic_id",
            "microchip",
            unique=True,
            postgresql_where=text("microchip IS NOT NULL AND deleted_at IS NULL"),
        ),
        {"schema": "vetsys"},
    )
    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("vetsys.clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    species: Mapped[str] = mapped_column(String(80))
    breed: Mapped[str | None] = mapped_column(String(120), default=None)
    sex: Mapped[str] = mapped_column(String(7), default="unknown", server_default="unknown")
    neutered: Mapped[bool | None] = mapped_column(Boolean, default=None)
    birth_date: Mapped[date | None] = mapped_column(Date, default=None)
    estimated_age_months: Mapped[int | None] = mapped_column(default=None)
    coat: Mapped[str | None] = mapped_column(String(120), default=None)
    microchip: Mapped[str | None] = mapped_column(String(50), default=None)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)


class TutorPatient(TenantModel):
    __tablename__ = "tutor_patients"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        UniqueConstraint("clinic_id", "patient_id", "tutor_id", name="uq_tutor_patient_pair"),
        Index(
            "uq_patient_primary_tutor",
            "clinic_id",
            "patient_id",
            unique=True,
            postgresql_where=text("is_primary AND deleted_at IS NULL"),
        ),
        Index("ix_link_patient", "clinic_id", "patient_id"),
        Index("ix_link_tutor", "clinic_id", "tutor_id"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    tutor_id: Mapped[UUID] = mapped_column()
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
