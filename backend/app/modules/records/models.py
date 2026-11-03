from datetime import date
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


def _author_columns() -> tuple[ForeignKeyConstraint, ...]:
    return (
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "author_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
    )


class RecordEntry(TenantModel):
    """Registro do art. 9º da Resolução CFMV 1321/2020; corrigir cria nova versão."""

    __tablename__ = "record_entries"
    __table_args__ = (
        *_author_columns(),
        UniqueConstraint("clinic_id", "id", name="uq_record_entry_clinic_id"),
        UniqueConstraint("clinic_id", "id", "patient_id", name="uq_record_entry_patient"),
        UniqueConstraint("clinic_id", "supersedes_id", name="uq_record_entry_supersedes"),
        UniqueConstraint("clinic_id", "root_id", "version", name="uq_record_entry_version"),
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            [
                "vetsys.encounters.clinic_id",
                "vetsys.encounters.id",
                "vetsys.encounters.patient_id",
            ],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [
                "vetsys.record_entries.clinic_id",
                "vetsys.record_entries.id",
                "vetsys.record_entries.patient_id",
            ],
        ),
        CheckConstraint("version >= 1", name="record_entry_version"),
        CheckConstraint(
            "(version = 1 AND supersedes_id IS NULL AND correction_reason IS NULL) OR "
            "(version > 1 AND supersedes_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="record_entry_correction",
        ),
        Index("ix_record_entry_patient", "clinic_id", "patient_id", "created_at"),
        Index("ix_record_entry_encounter", "clinic_id", "encounter_id"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    encounter_id: Mapped[UUID] = mapped_column()
    root_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[UUID | None] = mapped_column(default=None)
    correction_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    author_crmv: Mapped[str] = mapped_column(String(40))
    location: Mapped[str] = mapped_column(String(200))
    complaint: Mapped[str] = mapped_column(Text)
    general_state: Mapped[str] = mapped_column(Text)
    findings: Mapped[str | None] = mapped_column(Text, default=None)
    presumptive_diagnosis: Mapped[str] = mapped_column(Text)
    conclusive_diagnosis: Mapped[str | None] = mapped_column(Text, default=None)
    procedures: Mapped[str | None] = mapped_column(Text, default=None)
    prescription: Mapped[str | None] = mapped_column(Text, default=None)
    follow_up: Mapped[str | None] = mapped_column(String(500), default=None)


class WeightRecord(TenantModel):
    __tablename__ = "weight_records"
    __table_args__ = (
        *_author_columns(),
        UniqueConstraint("clinic_id", "id", name="uq_weight_record_clinic_id"),
        UniqueConstraint("clinic_id", "id", "patient_id", name="uq_weight_record_patient"),
        UniqueConstraint("clinic_id", "supersedes_id", name="uq_weight_record_supersedes"),
        ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [
                "vetsys.weight_records.clinic_id",
                "vetsys.weight_records.id",
                "vetsys.weight_records.patient_id",
            ],
        ),
        CheckConstraint("weight_grams > 0 AND weight_grams <= 5000000", name="weight_range"),
        CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="weight_correction"
        ),
        Index("ix_weight_record_patient", "clinic_id", "patient_id", "created_at"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    weight_grams: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[UUID | None] = mapped_column(default=None)
    correction_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))


class VaccineRecord(TenantModel):
    """Campos do art. 6º da Resolução CFMV 1321/2020 (carteira de vacinação)."""

    __tablename__ = "vaccine_records"
    __table_args__ = (
        *_author_columns(),
        UniqueConstraint("clinic_id", "id", name="uq_vaccine_record_clinic_id"),
        UniqueConstraint("clinic_id", "id", "patient_id", name="uq_vaccine_record_patient"),
        UniqueConstraint("clinic_id", "supersedes_id", name="uq_vaccine_record_supersedes"),
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            [
                "vetsys.encounters.clinic_id",
                "vetsys.encounters.id",
                "vetsys.encounters.patient_id",
            ],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [
                "vetsys.vaccine_records.clinic_id",
                "vetsys.vaccine_records.id",
                "vetsys.vaccine_records.patient_id",
            ],
        ),
        CheckConstraint("expires_on >= manufactured_on", name="vaccine_validity_order"),
        CheckConstraint(
            "(supersedes_id IS NULL) = (correction_reason IS NULL)", name="vaccine_correction"
        ),
        Index("ix_vaccine_record_patient", "clinic_id", "patient_id", "created_at"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    encounter_id: Mapped[UUID] = mapped_column()
    vaccine_name: Mapped[str] = mapped_column(String(200))
    batch: Mapped[str] = mapped_column(String(80))
    manufacturer: Mapped[str] = mapped_column(String(200))
    dose: Mapped[str] = mapped_column(String(80))
    manufactured_on: Mapped[date] = mapped_column(Date)
    expires_on: Mapped[date] = mapped_column(Date)
    next_dose_on: Mapped[date | None] = mapped_column(Date, default=None)
    supersedes_id: Mapped[UUID | None] = mapped_column(default=None)
    correction_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    author_crmv: Mapped[str] = mapped_column(String(40))


DOCUMENT_KINDS = ("lab_report", "external_history", "prescription", "other")
DOCUMENT_TYPES = ("application/pdf", "image/jpeg", "image/png")
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


class PatientDocument(TenantModel):
    """Laudo ou documento externo (art. 9º, X); arquivo, resumo ou os dois."""

    __tablename__ = "patient_documents"
    __table_args__ = (
        *_author_columns(),
        UniqueConstraint("clinic_id", "id", name="uq_patient_document_clinic_id"),
        UniqueConstraint("clinic_id", "id", "patient_id", name="uq_patient_document_patient"),
        UniqueConstraint("clinic_id", "supersedes_id", name="uq_patient_document_supersedes"),
        UniqueConstraint("clinic_id", "root_id", "version", name="uq_patient_document_version"),
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            [
                "vetsys.encounters.clinic_id",
                "vetsys.encounters.id",
                "vetsys.encounters.patient_id",
            ],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "supersedes_id", "patient_id"],
            [
                "vetsys.patient_documents.clinic_id",
                "vetsys.patient_documents.id",
                "vetsys.patient_documents.patient_id",
            ],
        ),
        CheckConstraint(
            "kind IN ('lab_report','external_history','prescription','other')",
            name="patient_document_kind",
        ),
        CheckConstraint("summary IS NOT NULL OR file_key IS NOT NULL", name="document_content"),
        CheckConstraint(
            "(file_key IS NULL) = (file_name IS NULL) AND (file_key IS NULL) = (sha256 IS NULL) "
            "AND (file_key IS NULL) = (size_bytes IS NULL) "
            "AND (file_key IS NULL) = (content_type IS NULL)",
            name="document_file_metadata",
        ),
        CheckConstraint(
            "content_type IS NULL OR content_type IN ('application/pdf','image/jpeg','image/png')",
            name="document_content_type",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR (size_bytes > 0 AND size_bytes <= 10485760)",
            name="document_size",
        ),
        CheckConstraint("sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="document_sha256"),
        CheckConstraint(
            "(version = 1 AND supersedes_id IS NULL AND correction_reason IS NULL) OR "
            "(version > 1 AND supersedes_id IS NOT NULL AND correction_reason IS NOT NULL)",
            name="document_correction",
        ),
        Index("ix_patient_document_patient", "clinic_id", "patient_id", "created_at"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    encounter_id: Mapped[UUID | None] = mapped_column(default=None)
    root_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    supersedes_id: Mapped[UUID | None] = mapped_column(default=None)
    correction_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    kind: Mapped[str] = mapped_column(String(20))
    origin_name: Mapped[str] = mapped_column(String(200))
    origin_crmv: Mapped[str | None] = mapped_column(String(40), default=None)
    document_date: Mapped[date] = mapped_column(Date)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    file_key: Mapped[str | None] = mapped_column(String(300), default=None)
    file_name: Mapped[str | None] = mapped_column(String(200), default=None)
    content_type: Mapped[str | None] = mapped_column(String(40), default=None)
    size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)
    sha256: Mapped[str | None] = mapped_column(String(64), default=None)
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    author_crmv: Mapped[str | None] = mapped_column(String(40), default=None)


class AuditLog(TenantModel):
    """Quem leu ou registrou prontuário. Nunca guarda conteúdo clínico."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "actor_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        CheckConstraint("action IN ('read','create','correct')", name="audit_action"),
        Index("ix_audit_log_patient", "clinic_id", "patient_id", "created_at"),
        {"schema": "vetsys"},
    )
    actor_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(10))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[UUID] = mapped_column()
    patient_id: Mapped[UUID] = mapped_column()
