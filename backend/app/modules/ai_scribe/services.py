import logging
from datetime import UTC, datetime
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from app.core.errors import BusinessConflict, ResourceNotFound, ServiceUnavailable
from app.core.repositories import ClinicContext
from app.modules.ai_scribe.models import AiDraft
from app.modules.ai_scribe.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from app.modules.ai_scribe.repositories import DraftRepository
from app.modules.ai_scribe.schemas import (
    DraftApproval,
    DraftContent,
    DraftGenerate,
    DraftRead,
)
from app.modules.clinics.models import User
from app.modules.records.schemas import Text
from app.modules.records.services import RecordService, require_clinical_reader, require_clinician
from app.providers.llm import LLMProvider
from app.providers.speech_to_text import SpeechToTextProvider

logger = logging.getLogger(__name__)


class ScribeService:
    @classmethod
    def for_clinic(
        cls, session: Session, context: ClinicContext, llm: LLMProvider, stt: SpeechToTextProvider
    ) -> "ScribeService":
        return cls(
            DraftRepository(session, context), RecordService.for_clinic(session, context), llm, stt
        )

    def __init__(
        self,
        drafts: DraftRepository,
        records: RecordService,
        llm: LLMProvider,
        stt: SpeechToTextProvider,
    ) -> None:
        self.drafts, self.records, self.llm, self.stt = drafts, records, llm, stt

    def _read(self, draft: AiDraft) -> DraftRead:
        return DraftRead(
            **{key: getattr(draft, key) for key in DraftRead.model_fields if key != "simulated"},
            simulated=draft.llm_provider == "mock" and draft.stt_provider in {None, "mock"},
        )

    def generate(self, actor: User, encounter_id: UUID, values: DraftGenerate) -> DraftRead:
        require_clinician(actor)
        encounter = self.records.scheduling.get_encounter(encounter_id)
        try:
            transcript = (
                self.stt.transcribe("consultation")
                if values.source == "mock_audio"
                else values.transcript
            )
            transcript = TypeAdapter(Text).validate_python(transcript)
            content = DraftContent.model_validate(
                self.llm.generate(transcript, prompt=SYSTEM_PROMPT)
            )
        except Exception:
            # Não registra a exceção: ela pode conter transcrição ou saída clínica inválida.
            logger.warning("Falha no provedor de scribe; conteúdo omitido")
            raise ServiceUnavailable(
                "Não foi possível gerar um rascunho válido. Tente novamente."
            ) from None
        draft = AiDraft(
            clinic_id=self.drafts.context.clinic_id,
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            requested_by=actor.id,
            source=values.source,
            transcript=transcript,
            content=content.model_dump(mode="json"),
            llm_provider=self.llm.name,
            llm_model=self.llm.model,
            stt_provider=self.stt.name if values.source == "mock_audio" else None,
            stt_model=self.stt.model if values.source == "mock_audio" else None,
            prompt_version=PROMPT_VERSION,
        )
        self.drafts.save(draft)
        self.records.audit_scribe(actor, "generate", draft.id, draft.patient_id)
        return self._read(draft)

    def list(self, actor: User, patient_id: UUID) -> list[DraftRead]:
        require_clinical_reader(actor)
        self.records.audit_scribe(actor, "list", patient_id, patient_id)
        return [self._read(draft) for draft in self.drafts.for_patient(patient_id)]

    def get(self, actor: User, draft_id: UUID) -> DraftRead:
        require_clinical_reader(actor)
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise ResourceNotFound("Rascunho não encontrado.")
        self.records.audit_scribe(actor, "read", draft.id, draft.patient_id)
        return self._read(draft)

    def _pending(self, actor: User, draft_id: UUID) -> AiDraft:
        require_clinician(actor)
        draft = self.drafts.locked(draft_id)
        if draft is None:
            raise ResourceNotFound("Rascunho não encontrado.")
        if draft.status != "pending":
            raise BusinessConflict("Este rascunho já foi aprovado ou descartado.")
        return draft

    def approve(self, actor: User, draft_id: UUID, values: DraftApproval) -> DraftRead:
        draft = self._pending(actor, draft_id)
        entry = self.records.add_entry(actor, draft.encounter_id, values.record)
        draft.status, draft.record_entry_id = "approved", entry.id
        draft.resolved_by, draft.resolved_at = actor.id, datetime.now(UTC)
        self.drafts.save(draft)
        self.records.audit_scribe(actor, "approve", draft.id, draft.patient_id)
        return self._read(draft)

    def discard(self, actor: User, draft_id: UUID) -> DraftRead:
        draft = self._pending(actor, draft_id)
        draft.status = "discarded"
        draft.resolved_by, draft.resolved_at = actor.id, datetime.now(UTC)
        self.drafts.save(draft)
        self.records.audit_scribe(actor, "discard", draft.id, draft.patient_id)
        return self._read(draft)
