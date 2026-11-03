from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MessageRead(BaseModel):
    id: UUID
    direction: str
    status: str
    phone: str
    body: str
    tutor_id: UUID | None
    tutor_name: str | None
    patient_id: UUID | None
    appointment_id: UUID | None
    intent: str | None
    needs_attention: bool
    handled_at: datetime | None
    created_at: datetime


class ReminderRead(BaseModel):
    id: UUID
    kind: str
    status: str
    due_at: datetime
    event_at: datetime
    patient_id: UUID
    patient_name: str
    outcome: str | None
    sent_at: datetime | None


class MessagingOverview(BaseModel):
    provider: str
    simulated: bool
    attention: list[MessageRead]
    upcoming: list[ReminderRead]
    recent_reminders: list[ReminderRead]
    messages: list[MessageRead]
    timezone: str = "America/Fortaleza"


class InboundInput(BaseModel):
    """Resposta simulada do tutor; o identificador opcional permite testar duplicatas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    phone: str = Field(min_length=8, max_length=30)
    body: str = Field(min_length=1, max_length=1000)
    provider_message_id: str | None = Field(default=None, min_length=1, max_length=200)


class DispatchResult(BaseModel):
    sent: int
    skipped: int
    failed: int
