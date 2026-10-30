from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class Tutor(TenantModel):
    __tablename__ = "tutors"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_tutor_clinic_id"),
        CheckConstraint(
            "NOT whatsapp_opt_in OR (phone IS NOT NULL AND whatsapp_opt_in_at "
            "IS NOT NULL AND whatsapp_opt_in_source IS NOT NULL)",
            name="valid_whatsapp_consent",
        ),
        {"schema": "vetsys"},
    )

    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("vetsys.clinics.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(16), default=None)
    document: Mapped[str | None] = mapped_column(String(30), default=None)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    whatsapp_opt_in_source: Mapped[str | None] = mapped_column(String(200), default=None)
    whatsapp_opt_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
