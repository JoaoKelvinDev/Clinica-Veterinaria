from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import AuthContext
from app.modules.messaging.schemas import (
    DispatchResult,
    InboundInput,
    MessageRead,
    MessagingOverview,
)
from app.modules.messaging.services import MessagingService
from app.providers.messaging import MessagingProvider

router = APIRouter(tags=["Mensagens"])


def messaging_service(request: Request, auth: AuthContext) -> MessagingService:
    return MessagingService.for_clinic(
        auth.session, auth.clinic, cast(MessagingProvider, request.app.state.messaging_provider)
    )


Service = Annotated[MessagingService, Depends(messaging_service)]


@router.get("/messaging", response_model=MessagingOverview)
def overview(auth: AuthContext, service: Service) -> MessagingOverview:
    return service.overview(auth.actor)


@router.post("/messaging/mock-inbound", response_model=MessageRead, status_code=201)
def mock_inbound(values: InboundInput, auth: AuthContext, service: Service) -> MessageRead:
    return service.receive(auth.actor, values.phone, values.body, values.provider_message_id)


@router.post("/messaging/dispatch-now", response_model=DispatchResult)
def dispatch_now(auth: AuthContext, service: Service) -> DispatchResult:
    return service.dispatch_now(auth.actor)


@router.post("/messages/{message_id}/handled", response_model=MessageRead)
def handled(message_id: UUID, auth: AuthContext, service: Service) -> MessageRead:
    return service.mark_handled(auth.actor, message_id)
