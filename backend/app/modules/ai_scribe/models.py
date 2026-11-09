from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class AiDraft(TenantModel):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        UniqueConstraint("clinic_id", "record_entry_id", name="uq_ai_draft_record"),
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            ["vetsys.encounters.clinic_id", "vetsys.encounters.id", "vetsys.encounters.patient_id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "requested_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "resolved_by"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "record_entry_id", "patient_id"],
            [
                "vetsys.record_entries.clinic_id",
                "vetsys.record_entries.id",
                "vetsys.record_entries.patient_id",
            ],
        ),
        CheckConstraint("source IN ('text','mock_audio')", name="ai_draft_source"),
        CheckConstraint("length(transcript) BETWEEN 1 AND 20000", name="ai_draft_transcript"),
        CheckConstraint("jsonb_typeof(content) = 'object'", name="ai_draft_content"),
        CheckConstraint("deleted_at IS NULL", name="ai_draft_preserved"),
        CheckConstraint(
            "(status = 'pending' AND resolved_by IS NULL AND resolved_at IS NULL "
            "AND record_entry_id IS NULL) OR "
            "(status = 'approved' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL "
            "AND record_entry_id IS NOT NULL) OR "
            "(status = 'discarded' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL "
            "AND record_entry_id IS NULL)",
            name="ai_draft_resolution",
        ),
        Index("ix_ai_draft_patient", "clinic_id", "patient_id", "created_at"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    encounter_id: Mapped[UUID] = mapped_column()
    source: Mapped[str] = mapped_column(String(20))
    transcript: Mapped[str] = mapped_column(Text)
    content: Mapped[dict[str, object]] = mapped_column(JSONB)
    requested_by: Mapped[UUID] = mapped_column()
    llm_provider: Mapped[str] = mapped_column(String(80))
    llm_model: Mapped[str] = mapped_column(String(100))
    stt_provider: Mapped[str | None] = mapped_column(String(80), default=None)
    stt_model: Mapped[str | None] = mapped_column(String(100), default=None)
    prompt_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")
    resolved_by: Mapped[UUID | None] = mapped_column(default=None)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    record_entry_id: Mapped[UUID | None] = mapped_column(default=None)
