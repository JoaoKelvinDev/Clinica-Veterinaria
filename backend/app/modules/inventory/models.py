from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, ForeignKeyConstraint, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import TenantModel


class Product(TenantModel):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("clinic_id", "id", name="uq_product_clinic"),
        {"schema": "vetsys"},
    )
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(9, 3))
    track_expiry: Mapped[bool] = mapped_column()
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class Lot(TenantModel):
    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("clinic_id", "product_id", "code", name="uq_lot_code"),
        UniqueConstraint("clinic_id", "product_id", "id", name="uq_lot_product"),
        ForeignKeyConstraint(
            ["clinic_id", "product_id"], ["vetsys.products.clinic_id", "vetsys.products.id"]
        ),
        {"schema": "vetsys"},
    )
    product_id: Mapped[UUID] = mapped_column()
    code: Mapped[str] = mapped_column(String(80))
    expires_on: Mapped[date | None] = mapped_column(Date, default=None)


class StockMovement(TenantModel):
    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint("clinic_id", "product_id", "lot_id", "id", name="uq_movement_lot"),
        ForeignKeyConstraint(
            ["clinic_id", "product_id", "lot_id"],
            ["vetsys.lots.clinic_id", "vetsys.lots.product_id", "vetsys.lots.id"],
        ),
        ForeignKeyConstraint(
            ["clinic_id", "author_id"], ["vetsys.users.clinic_id", "vetsys.users.id"]
        ),
        ForeignKeyConstraint(
            ["clinic_id", "product_id", "lot_id", "corrects_id"],
            [
                "vetsys.stock_movements.clinic_id",
                "vetsys.stock_movements.product_id",
                "vetsys.stock_movements.lot_id",
                "vetsys.stock_movements.id",
            ],
        ),
        Index("ix_stock_ledger", "clinic_id", "product_id", "lot_id", "created_at"),
        {"schema": "vetsys"},
    )
    product_id: Mapped[UUID] = mapped_column()
    lot_id: Mapped[UUID] = mapped_column()
    operation_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(12))
    quantity: Mapped[Decimal] = mapped_column(Numeric(9, 3))
    reason: Mapped[str] = mapped_column(String(500))
    author_id: Mapped[UUID] = mapped_column()
    author_name: Mapped[str] = mapped_column(String(200))
    product_name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    corrects_id: Mapped[UUID | None] = mapped_column(default=None)
