from typing import cast

from fastapi import APIRouter, Request, Response

from app.core.dependencies import ConsistentAuthContext
from app.modules.dashboard.schemas import DashboardRead
from app.modules.dashboard.services import DashboardService
from app.providers.messaging import MessagingProvider

router = APIRouter(tags=["Visão geral"])


@router.get("/dashboard", response_model=DashboardRead)
def dashboard(auth: ConsistentAuthContext, request: Request, response: Response) -> DashboardRead:
    response.headers["Cache-Control"] = "no-store"
    service = DashboardService.for_clinic(
        auth.session, auth.clinic, cast(MessagingProvider, request.app.state.messaging_provider)
    )
    return service.read(auth.actor)
