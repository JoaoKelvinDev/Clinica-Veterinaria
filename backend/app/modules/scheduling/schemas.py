from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.modules.scheduling.models import AppointmentStatus


class AppointmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_id: UUID
    veterinarian_id: UUID
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    kind: str = Field(min_length=1, max_length=80)


class AppointmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    patient_id: UUID | None = None
    veterinarian_id: UUID | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    kind: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def nonempty_patch(self) -> Self:
        if not self.model_fields_set or any(
            getattr(self, field) is None for field in self.model_fields_set
        ):
            raise ValueError("Informe campos não nulos para reagendar")
        return self


class StatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: AppointmentStatus


class AppointmentRead(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    patient_name: str
    veterinarian_id: UUID
    veterinarian_name: str
    starts_at: datetime
    ends_at: datetime
    kind: str
    status: AppointmentStatus
    encounter_id: UUID | None


class AppointmentPage(BaseModel):
    items: list[AppointmentRead]
    total: int
    timezone: str = "America/Fortaleza"


class EncounterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID


class EncounterRead(BaseModel):
    id: UUID
    clinic_id: UUID
    patient_id: UUID
    patient_name: str
    veterinarian_id: UUID
    veterinarian_name: str
    appointment_id: UUID | None
    started_at: datetime
    completed_at: datetime | None


class EncounterPage(BaseModel):
    items: list[EncounterRead]
    total: int
    timezone: str = "America/Fortaleza"


class ScheduleSummary(BaseModel):
    appointments_total: int = Field(ge=0)
    scheduled: int = Field(ge=0)
    confirmed: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    completed: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    no_show: int = Field(ge=0)
    open_encounters: int = Field(ge=0)
