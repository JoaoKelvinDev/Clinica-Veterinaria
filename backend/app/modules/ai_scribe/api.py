from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.core.dependencies import AuthContext
from app.modules.ai_scribe.schemas import DraftApproval, DraftGenerate, DraftRead
from app.modules.ai_scribe.services import ScribeService
from app.providers.llm import LLMProvider
from app.providers.speech_to_text import SpeechToTextProvider

router = APIRouter(tags=["Scribe (MOCK)"])


def scribe_service(request: Request, auth: AuthContext) -> ScribeService:
    return ScribeService.for_clinic(
        auth.session,
        auth.clinic,
        cast(LLMProvider, request.app.state.llm_provider),
        cast(SpeechToTextProvider, request.app.state.stt_provider),
    )


Service = Annotated[ScribeService, Depends(scribe_service)]


@router.post("/encounters/{encounter_id}/ai-drafts", response_model=DraftRead, status_code=201)
def generate(
    encounter_id: UUID, values: DraftGenerate, auth: AuthContext, service: Service
) -> DraftRead:
    return service.generate(auth.actor, encounter_id, values)


@router.get("/patients/{patient_id}/ai-drafts", response_model=list[DraftRead])
def list_drafts(patient_id: UUID, auth: AuthContext, service: Service) -> list[DraftRead]:
    return service.list(auth.actor, patient_id)


@router.get("/ai-drafts/{draft_id}", response_model=DraftRead)
def get_draft(draft_id: UUID, auth: AuthContext, service: Service) -> DraftRead:
    return service.get(auth.actor, draft_id)


@router.post("/ai-drafts/{draft_id}/approve", response_model=DraftRead)
def approve(
    draft_id: UUID, values: DraftApproval, auth: AuthContext, service: Service
) -> DraftRead:
    return service.approve(auth.actor, draft_id, values)


@router.post("/ai-drafts/{draft_id}/discard", response_model=DraftRead)
def discard(draft_id: UUID, auth: AuthContext, service: Service) -> DraftRead:
    return service.discard(auth.actor, draft_id)
