from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class FinancialEntry(TenantModel):
    __tablename__ = "financial_entries"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_financial_clinic"),
        UniqueConstraint("clinic_id", "reverses_id", name="uq_financial_reversal"),
        *(
            ForeignKeyConstraint(
                ["clinic_id", field], [f"vetsys.{table}.clinic_id", f"vetsys.{table}.id"]
            )
            for field, table in (
                ("author_id", "users"),
                ("tutor_id", "tutors"),
                ("patient_id", "patients"),
                ("reverses_id", "financial_entries"),
            )
        ),
        Index("ix_financial_period", "clinic_id", "occurred_on", "id"),
        {"schema": "vetsys"},
    )
    kind: Mapped[str] = mapped_column(String(7))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(80))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    occurred_on: Mapped[date] = mapped_column(Date)
    payment_method: Mapped[str] = mapped_column(String(20))
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    tutor_id: Mapped[UUID | None] = mapped_column(default=None)
    tutor_name: Mapped[str | None] = mapped_column(String(200), default=None)
    patient_id: Mapped[UUID | None] = mapped_column(default=None)
    patient_name: Mapped[str | None] = mapped_column(String(200), default=None)
    reverses_id: Mapped[UUID | None] = mapped_column(default=None)
    reversal_reason: Mapped[str | None] = mapped_column(String(500), default=None)
