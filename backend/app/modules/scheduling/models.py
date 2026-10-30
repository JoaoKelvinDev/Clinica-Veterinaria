from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class AppointmentStatus(StrEnum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(TenantModel):
    __tablename__ = "appointments"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_appointment_clinic_id"),
        UniqueConstraint(
            "clinic_id", "id", "patient_id", "veterinarian_id", name="uq_appointment_identity"
        ),
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "veterinarian_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        CheckConstraint("ends_at > starts_at", name="appointment_positive_duration"),
        CheckConstraint(
            "status IN ('scheduled','confirmed','in_progress','completed','cancelled','no_show')",
            name="appointment_status",
        ),
        ExcludeConstraint(
            ("clinic_id", "="),
            ("veterinarian_id", "="),
            (text("tstzrange(starts_at, ends_at, '[)')"), "&&"),
            where=text("status NOT IN ('cancelled','no_show')"),
            name="no_veterinarian_overlap",
            using="gist",
        ),
        Index("ix_appointment_day", "clinic_id", "starts_at"),
        Index("ix_appointment_veterinarian", "clinic_id", "veterinarian_id", "starts_at"),
        Index("ix_appointment_patient", "clinic_id", "patient_id"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    veterinarian_id: Mapped[UUID] = mapped_column()
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    kind: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12), default="scheduled", server_default="scheduled")


class Encounter(TenantModel):
    __tablename__ = "encounters"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_encounter_clinic_id"),
        UniqueConstraint("clinic_id", "appointment_id", name="uq_encounter_appointment"),
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "veterinarian_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "appointment_id", "patient_id", "veterinarian_id"],
            [
                "vetsys.appointments.clinic_id",
                "vetsys.appointments.id",
                "vetsys.appointments.patient_id",
                "vetsys.appointments.veterinarian_id",
            ],
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at", name="encounter_completion_order"
        ),
        Index("ix_encounter_day", "clinic_id", "started_at"),
        Index("ix_encounter_veterinarian", "clinic_id", "veterinarian_id", "started_at"),
        Index("ix_encounter_patient", "clinic_id", "patient_id"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    veterinarian_id: Mapped[UUID] = mapped_column()
    appointment_id: Mapped[UUID | None] = mapped_column(default=None)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
