from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def exact_quantity(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Use uma quantidade decimal em texto.")
    return value


Quantity = Annotated[
    Decimal,
    BeforeValidator(exact_quantity),
    Field(gt=0, le=Decimal("999999.999"), max_digits=9, decimal_places=3, allow_inf_nan=False),
]
Minimum = Annotated[
    Decimal,
    BeforeValidator(exact_quantity),
    Field(ge=0, le=Decimal("999999.999"), max_digits=9, decimal_places=3, allow_inf_nan=False),
]
Delta = Annotated[
    Decimal,
    BeforeValidator(exact_quantity),
    Field(
        ge=Decimal("-999999.999"),
        le=Decimal("999999.999"),
        max_digits=9,
        decimal_places=3,
        allow_inf_nan=False,
    ),
]
Text = Annotated[str, Field(min_length=1, max_length=200)]
Reason = Annotated[str, Field(min_length=3, max_length=500)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VersionInput(Input):
    expected_version: int = Field(strict=True, ge=1)


class ProductCreate(Input):
    name: Text
    unit: str = Field(min_length=1, max_length=20)
    minimum_stock: Minimum
    track_expiry: bool = Field(strict=True)


class ProductEdit(ProductCreate, VersionInput):
    pass


class LotCreate(VersionInput):
    code: str = Field(min_length=1, max_length=80)
    expires_on: date | None = None


class Receipt(VersionInput):
    lot_id: UUID
    quantity: Quantity
    reason: Reason


class Issue(VersionInput):
    quantity: Quantity
    reason: Reason


class Adjustment(VersionInput):
    lot_id: UUID
    quantity: Delta
    reason: Reason
    corrects_id: UUID | None = None


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    unit: str
    minimum_stock: Decimal
    track_expiry: bool
    version: int
    deleted_at: datetime | None
    physical_stock: Decimal
    available_stock: Decimal
    expired_stock: Decimal
    low_stock: bool
    expiring_lots: int
    expired_lots: int


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    expires_on: date | None
    balance: Decimal
    expired: bool
    expiring: bool


class MovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lot_id: UUID
    operation_id: UUID
    kind: Literal["inbound", "outbound", "adjustment"]
    quantity: Decimal
    reason: str
    author_name: str
    product_name: str
    unit: str
    created_at: datetime
    corrects_id: UUID | None


class ProductRead(ProductSummary):
    lots: list[LotRead]


class ProductPage(BaseModel):
    items: list[ProductSummary]
    total: int


class MovementPage(BaseModel):
    items: list[MovementRead]
    total: int


class InventoryAlerts(BaseModel):
    low_stock_products: int = Field(ge=0)
    expired_lots: int = Field(ge=0)
    expiring_lots: int = Field(ge=0)
