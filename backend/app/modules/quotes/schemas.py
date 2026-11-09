from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, model_validator

MAX_CENTS = 1_000_000_000_000
Money = Annotated[StrictInt, Field(ge=0, le=MAX_CENTS)]
Version = Annotated[StrictInt, Field(ge=1)]
QuoteStatus = Literal["draft", "sent", "approved", "rejected", "expired"]
DecisionSource = Literal["in_person", "phone", "other"]


def exact_quantity(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Envie a quantidade como texto decimal ou inteiro")
    return value


Quantity = Annotated[
    Decimal,
    BeforeValidator(exact_quantity),
    Field(gt=0, le=Decimal("999999.999"), max_digits=9, decimal_places=3, allow_inf_nan=False),
]


class QuoteItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Literal["service", "product"]
    description: str = Field(min_length=1, max_length=300)
    quantity: Quantity
    unit_price_cents: Money


class QuoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_id: UUID
    tutor_id: UUID
    encounter_id: UUID | None = None
    valid_until: date | None = None
    discount_cents: Money = 0
    items: list[QuoteItemInput] = Field(min_length=1, max_length=100)


class QuoteEdit(QuoteCreate):
    expected_version: Version


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: Version


class QuoteDecision(VersionInput):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: DecisionSource
    note: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def describe_other_source(self) -> Self:
        if self.source == "other" and self.note is None:
            raise ValueError("Descreva a origem da decisão")
        return self


class QuoteItemRead(QuoteItemInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    position: int
    line_total_cents: int


class QuoteSummary(BaseModel):
    id: UUID
    patient_id: UUID
    tutor_id: UUID
    patient_name: str
    tutor_name: str
    encounter_id: UUID | None
    source_quote_id: UUID | None
    status: QuoteStatus
    version: int
    valid_until: date | None
    subtotal_cents: int
    discount_cents: int
    total_cents: int
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID
    presented_at: datetime | None
    presented_by: UUID | None
    decision_at: datetime | None
    decision_by: UUID | None
    decision_source: DecisionSource | None
    decision_note: str | None


class QuoteRead(QuoteSummary):
    items: list[QuoteItemRead]


class QuotePage(BaseModel):
    items: list[QuoteSummary]
    total: int


class TutorOption(BaseModel):
    id: UUID
    name: str
    is_primary: bool


class EncounterOption(BaseModel):
    id: UUID
    started_at: datetime
    veterinarian_name: str


class QuoteOptions(BaseModel):
    tutors: list[TutorOption]
    encounters: list[EncounterOption]
