from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class ReminderKind(StrEnum):
    APPOINTMENT_CONFIRMATION = "appointment_confirmation"
    APPOINTMENT_REMINDER = "appointment_reminder"
    VACCINE = "vaccine"
    FOLLOW_UP = "follow_up"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ReminderJob(TenantModel):
    """Lembrete agendado; `dedupe_key` torna o planejamento idempotente."""

    __tablename__ = "reminder_jobs"
    __table_args__ = (
        UniqueConstraint("clinic_id", "dedupe_key", name="uq_reminder_dedupe"),
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["vetsys.appointments.clinic_id", "vetsys.appointments.id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "vaccine_record_id"],
            ["vetsys.vaccine_records.clinic_id", "vetsys.vaccine_records.id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "record_entry_id"],
            ["vetsys.record_entries.clinic_id", "vetsys.record_entries.id"],
        ),
        CheckConstraint(
            "kind IN ('appointment_confirmation','appointment_reminder','vaccine','follow_up')",
            name="reminder_kind",
        ),
        CheckConstraint(
            "status IN ('pending','sent','skipped','cancelled','failed')", name="reminder_status"
        ),
        CheckConstraint(
            "num_nonnulls(appointment_id, vaccine_record_id, record_entry_id) = 1",
            name="reminder_single_source",
        ),
        Index("ix_reminder_due", "status", "due_at"),
        Index("ix_reminder_clinic_due", "clinic_id", "status", "due_at"),
        {"schema": "vetsys"},
    )
    kind: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(10), default="pending", server_default="pending")
    dedupe_key: Mapped[str] = mapped_column(String(200))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Data do evento lembrado: o worker monta o texto sem ler tabelas clínicas.
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    patient_id: Mapped[UUID] = mapped_column()
    appointment_id: Mapped[UUID | None] = mapped_column(default=None)
    vaccine_record_id: Mapped[UUID | None] = mapped_column(default=None)
    record_entry_id: Mapped[UUID | None] = mapped_column(default=None)
    outcome: Mapped[str | None] = mapped_column(String(200), default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Message(TenantModel):
    """Mensagem enviada ou recebida. O par provedor/identificador impede duplicatas."""

    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("provider", "provider_message_id", name="uq_message_provider_id"),
        ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "appointment_id"],
            ["vetsys.appointments.clinic_id", "vetsys.appointments.id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "handled_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        CheckConstraint("direction IN ('outbound','inbound')", name="message_direction"),
        CheckConstraint("status IN ('sent','failed','received')", name="message_status"),
        CheckConstraint(
            "intent IS NULL OR intent IN ('confirm','cancel','opt_out','unknown')",
            name="message_intent",
        ),
        Index("ix_message_clinic_created", "clinic_id", "created_at"),
        Index("ix_message_phone", "clinic_id", "phone", "created_at"),
        {"schema": "vetsys"},
    )
    direction: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10))
    provider: Mapped[str] = mapped_column(String(20))
    provider_message_id: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    tutor_id: Mapped[UUID | None] = mapped_column(default=None)
    patient_id: Mapped[UUID | None] = mapped_column(default=None)
    appointment_id: Mapped[UUID | None] = mapped_column(default=None)
    reminder_job_id: Mapped[UUID | None] = mapped_column(default=None)
    intent: Mapped[str | None] = mapped_column(String(10), default=None)
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    handled_by: Mapped[UUID | None] = mapped_column(default=None)
