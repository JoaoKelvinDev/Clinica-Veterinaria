from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class Quote(TenantModel):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_quote_clinic_id"),
        ForeignKeyConstraint(
            ["clinic_id", "patient_id"], ["vetsys.patients.clinic_id", "vetsys.patients.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "tutor_id"], ["vetsys.tutors.clinic_id", "vetsys.tutors.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "encounter_id", "patient_id"],
            ["vetsys.encounters.clinic_id", "vetsys.encounters.id", "vetsys.encounters.patient_id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "source_quote_id"], ["vetsys.quotes.clinic_id", "vetsys.quotes.id"]
        ),
        *(
            ForeignKeyConstraint(
                ["clinic_id", column], ["vetsys.users.clinic_id", "vetsys.users.id"]
            )
            for column in ("created_by", "updated_by", "presented_by", "decision_by")
        ),
        CheckConstraint("status IN ('draft','sent','approved','rejected')", name="quote_status"),
        CheckConstraint("version >= 1", name="quote_version"),
        CheckConstraint(
            "subtotal_cents BETWEEN 0 AND 1000000000000 "
            "AND discount_cents BETWEEN 0 AND subtotal_cents "
            "AND total_cents = subtotal_cents - discount_cents",
            name="quote_totals",
        ),
        CheckConstraint("deleted_at IS NULL", name="quote_preserved"),
        CheckConstraint(
            "(status = 'draft' AND presented_at IS NULL AND presented_by IS NULL) "
            "OR (status <> 'draft' AND presented_at IS NOT NULL AND presented_by IS NOT NULL)",
            name="quote_presentation",
        ),
        CheckConstraint(
            "(status IN ('draft','sent') AND decision_at IS NULL AND decision_by IS NULL "
            "AND decision_source IS NULL AND decision_note IS NULL) "
            "OR (status IN ('approved','rejected') AND decision_at IS NOT NULL "
            "AND decision_by IS NOT NULL AND decision_source IN ('in_person','phone','other'))",
            name="quote_decision",
        ),
        Index("ix_quote_patient", "clinic_id", "patient_id", "created_at"),
        Index("ix_quote_list", "clinic_id", "created_at"),
        {"schema": "vetsys"},
    )
    patient_id: Mapped[UUID] = mapped_column()
    tutor_id: Mapped[UUID] = mapped_column()
    patient_name: Mapped[str] = mapped_column(String(200))
    tutor_name: Mapped[str] = mapped_column(String(200))
    encounter_id: Mapped[UUID | None] = mapped_column(default=None)
    source_quote_id: Mapped[UUID | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    valid_until: Mapped[date | None] = mapped_column(Date, default=None)
    subtotal_cents: Mapped[int] = mapped_column(BigInteger)
    discount_cents: Mapped[int] = mapped_column(BigInteger)
    total_cents: Mapped[int] = mapped_column(BigInteger)
    created_by: Mapped[UUID] = mapped_column()
    updated_by: Mapped[UUID] = mapped_column()
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    presented_by: Mapped[UUID | None] = mapped_column(default=None)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    decision_by: Mapped[UUID | None] = mapped_column(default=None)
    decision_source: Mapped[str | None] = mapped_column(String(20), default=None)
    decision_note: Mapped[str | None] = mapped_column(String(500), default=None)


class QuoteItem(TenantModel):
    __tablename__ = "quote_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["clinic_id", "quote_id"], ["vetsys.quotes.clinic_id", "vetsys.quotes.id"]
        ),
        UniqueConstraint("clinic_id", "quote_id", "position", name="uq_quote_item_position"),
        CheckConstraint("position BETWEEN 1 AND 100", name="quote_item_position"),
        CheckConstraint("kind IN ('service','product')", name="quote_item_kind"),
        CheckConstraint("quantity > 0 AND quantity <= 999999.999", name="quote_item_quantity"),
        CheckConstraint(
            "unit_price_cents BETWEEN 0 AND 1000000000000 "
            "AND line_total_cents BETWEEN 0 AND 1000000000000",
            name="quote_item_money",
        ),
        CheckConstraint("deleted_at IS NULL", name="quote_item_preserved"),
        {"schema": "vetsys"},
    )
    quote_id: Mapped[UUID] = mapped_column()
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Numeric(9, 3))
    unit_price_cents: Mapped[int] = mapped_column(BigInteger)
    line_total_cents: Mapped[int] = mapped_column(
        BigInteger, Computed("round(quantity * unit_price_cents)", persisted=True)
    )
