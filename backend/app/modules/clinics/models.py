from enum import StrEnum
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class Role(StrEnum):
    ADMIN = "admin"
    VETERINARIAN = "veterinarian"
    ASSISTANT = "assistant"
    RECEPTION = "reception"


class Clinic(TenantModel):
    __tablename__ = "clinics"
    __table_args__ = (
        CheckConstraint("clinic_id = id", name="clinic_is_tenant"),
        {"schema": "vetsys"},
    )

    name: Mapped[str] = mapped_column(String(200))


class User(TenantModel):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_user_clinic_id"),
        CheckConstraint(
            "role <> 'veterinarian' OR (crmv IS NOT NULL AND crmv_state IS NOT NULL)",
            name="veterinarian_has_crmv",
        ),
        {"schema": "vetsys"},
    )

    clinic_id: Mapped[UUID] = mapped_column(ForeignKey("vetsys.clinics.id"), index=True)
    auth_id: Mapped[UUID] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(
        Enum(
            Role,
            values_callable=lambda values: [v.value for v in values],
            native_enum=False,
            create_constraint=True,
            name="user_role",
        )
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    crmv: Mapped[str | None] = mapped_column(String(30), default=None)
    crmv_state: Mapped[str | None] = mapped_column(String(2), default=None)
