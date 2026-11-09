from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import AuthContext
from app.modules.quotes.schemas import (
    QuoteCreate,
    QuoteDecision,
    QuoteEdit,
    QuoteOptions,
    QuotePage,
    QuoteRead,
    QuoteStatus,
    VersionInput,
)
from app.modules.quotes.services import QuoteService

router = APIRouter(tags=["Orçamentos"])


def quote_service(auth: AuthContext) -> QuoteService:
    return QuoteService.for_clinic(auth.session, auth.clinic)


Service = Annotated[QuoteService, Depends(quote_service)]


@router.get("/quotes", response_model=QuotePage)
def list_quotes(
    service: Service,
    q: str = Query(default="", max_length=100),
    status: QuoteStatus | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> QuotePage:
    return service.list(q, status, limit, offset)


@router.get("/quotes/options/{patient_id}", response_model=QuoteOptions)
def options(patient_id: UUID, service: Service) -> QuoteOptions:
    return service.options(patient_id)


@router.get("/quotes/{quote_id}", response_model=QuoteRead)
def get_quote(quote_id: UUID, service: Service) -> QuoteRead:
    return service.get(quote_id)


@router.post("/quotes", response_model=QuoteRead, status_code=201)
def create_quote(values: QuoteCreate, auth: AuthContext, service: Service) -> QuoteRead:
    return service.create(auth.actor, values)


@router.put("/quotes/{quote_id}", response_model=QuoteRead)
def edit_quote(quote_id: UUID, values: QuoteEdit, auth: AuthContext, service: Service) -> QuoteRead:
    return service.edit(auth.actor, quote_id, values)


@router.post("/quotes/{quote_id}/present", response_model=QuoteRead)
def present(quote_id: UUID, values: VersionInput, auth: AuthContext, service: Service) -> QuoteRead:
    return service.present(auth.actor, quote_id, values.expected_version)


@router.post("/quotes/{quote_id}/approve", response_model=QuoteRead)
def approve(
    quote_id: UUID, values: QuoteDecision, auth: AuthContext, service: Service
) -> QuoteRead:
    return service.decide(auth.actor, quote_id, values, approve=True)


@router.post("/quotes/{quote_id}/reject", response_model=QuoteRead)
def reject(quote_id: UUID, values: QuoteDecision, auth: AuthContext, service: Service) -> QuoteRead:
    return service.decide(auth.actor, quote_id, values, approve=False)


@router.post("/quotes/{quote_id}/revise", response_model=QuoteRead, status_code=201)
def revise(quote_id: UUID, values: VersionInput, auth: AuthContext, service: Service) -> QuoteRead:
    return service.revise(auth.actor, quote_id, values.expected_version)
