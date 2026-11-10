from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

MAX_CENTS = 1_000_000_000_000
EntryKind = Literal["income", "expense"]
PaymentMethod = Literal["cash", "pix", "debit_card", "credit_card", "bank_transfer", "other"]
EntryStatus = Literal["posted", "reversed"]


class EntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: EntryKind
    description: str = Field(min_length=1, max_length=300)
    category: str = Field(min_length=1, max_length=80)
    amount_cents: Annotated[StrictInt, Field(gt=0, le=MAX_CENTS)]
    occurred_on: date
    payment_method: PaymentMethod
    tutor_id: UUID | None = None
    patient_id: UUID | None = None


class ReversalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)


class ReversalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author_id: UUID
    author_name: str
    created_at: datetime
    reversal_reason: str


class EntryRead(EntryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    author_id: UUID
    author_name: str
    created_at: datetime
    tutor_name: str | None
    patient_name: str | None
    status: EntryStatus = "posted"
    reversal: ReversalRead | None = None


class FinancialSummary(BaseModel):
    # Inteiros decimais como texto no transporte evitam arredondar somas no JavaScript.
    income_cents: str
    expense_cents: str | None
    difference_cents: str | None


class EntryPage(BaseModel):
    items: list[EntryRead]
    total: int
    summary: FinancialSummary


class EntryFilters(BaseModel):
    start: date
    end: date
    q: str = ""
    category: str = ""
    payment_method: PaymentMethod | None = None
    kind: EntryKind | None = None
    status: EntryStatus | None = None
