from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.modules.records.schemas import RecordEntryCreate, Text


class DraftContent(BaseModel):
    """Campos SOAP compatíveis com o prontuário; ausências não são preenchidas pela IA."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, strict=True)
    complaint: Text | None = None
    general_state: Text | None = None
    findings: Text | None = None
    presumptive_diagnosis: Text | None = None
    conclusive_diagnosis: Text | None = None
    procedures: Text | None = None
    prescription: Text | None = None
    follow_up: str | None = Field(default=None, min_length=1, max_length=500)
    uncertainties: list[str] = Field(max_length=20)

    @model_validator(mode="after")
    def bounded_uncertainties(self) -> Self:
        if any(not item.strip() or len(item) > 500 for item in self.uncertainties):
            raise ValueError("Incertezas inválidas")
        return self


class DraftGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: Literal["text", "mock_audio"] = "text"
    transcript: Text | None = None
    sample_id: Literal["consultation"] | None = None

    @model_validator(mode="after")
    def matching_source(self) -> Self:
        if self.source == "text" and (self.transcript is None or self.sample_id is not None):
            raise ValueError("Informe somente a transcrição")
        if self.source == "mock_audio" and (
            self.transcript is not None or self.sample_id != "consultation"
        ):
            raise ValueError("Selecione o exemplo MOCK")
        return self


class DraftApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_confirmed: StrictBool
    record: RecordEntryCreate

    @model_validator(mode="after")
    def explicit_review(self) -> Self:
        if not self.review_confirmed:
            raise ValueError("Confirme a revisão")
        if self.record.supersedes_id is not None:
            raise ValueError("Aprovar cria um registro novo; não corrige outro registro")
        return self


class DraftRead(BaseModel):
    id: UUID
    patient_id: UUID
    encounter_id: UUID
    source: Literal["text", "mock_audio"]
    transcript: str
    content: DraftContent
    requested_by: UUID
    llm_provider: str
    llm_model: str
    stt_provider: str | None
    stt_model: str | None
    prompt_version: str
    status: Literal["pending", "approved", "discarded"]
    resolved_by: UUID | None
    resolved_at: datetime | None
    record_entry_id: UUID | None
    created_at: datetime
    simulated: bool
