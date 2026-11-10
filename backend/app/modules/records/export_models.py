from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class RecordExport(TenantModel):
    __tablename__ = "record_exports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "author_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        CheckConstraint("deleted_at IS NULL", name="record_export_preserved"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="record_export_hash"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="record_export_size"),
        CheckConstraint(
            "attachment_count >= 0 AND missing_file_count >= 0", name="record_export_counts"
        ),
        Index("ix_record_export_patient", "clinic_id", "patient_id", "created_at", "id"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    tutor_id: Mapped[UUID] = mapped_column()
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    author_crmv: Mapped[str] = mapped_column(String(40))
    tutor_name: Mapped[str] = mapped_column(String(200))
    file_key: Mapped[str] = mapped_column(String(300), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    attachment_count: Mapped[int] = mapped_column(Integer)
    missing_file_count: Mapped[int] = mapped_column(Integer)
    attachments: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
