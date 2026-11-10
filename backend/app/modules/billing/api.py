from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AuthContext, ConsistentAuthContext
from app.modules.billing.schemas import (
    EntryCreate,
    EntryFilters,
    EntryKind,
    EntryPage,
    EntryRead,
    EntryStatus,
    PaymentMethod,
    ReversalCreate,
)
from app.modules.billing.services import FinancialService

router = APIRouter(prefix="/financial/entries", tags=["Financeiro"])


def filters(
    start: date,
    end: date,
    q: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=80),
    payment_method: PaymentMethod | None = None,
    kind: EntryKind | None = None,
    status: EntryStatus | None = None,
) -> EntryFilters:
    return EntryFilters(
        start=start,
        end=end,
        q=q.strip(),
        category=category.strip(),
        payment_method=payment_method,
        kind=kind,
        status=status,
    )


@router.get("", response_model=EntryPage)
def list_entries(
    auth: ConsistentAuthContext,
    values: Annotated[EntryFilters, Depends(filters)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> EntryPage:
    return FinancialService.for_clinic(auth.session, auth.clinic).list(
        auth.actor, values, limit, offset
    )


@router.get("/{entry_id}", response_model=EntryRead)
def get_entry(entry_id: UUID, auth: ConsistentAuthContext) -> EntryRead:
    return FinancialService.for_clinic(auth.session, auth.clinic).get(auth.actor, entry_id)


@router.post("", response_model=EntryRead, status_code=201)
def create_entry(values: EntryCreate, auth: AuthContext) -> EntryRead:
    return FinancialService.for_clinic(auth.session, auth.clinic).create(auth.actor, values)


@router.post("/{entry_id}/reverse", response_model=EntryRead, status_code=201)
def reverse_entry(entry_id: UUID, values: ReversalCreate, auth: AuthContext) -> EntryRead:
    return FinancialService.for_clinic(auth.session, auth.clinic).reverse(
        auth.actor, entry_id, values.reason
    )
