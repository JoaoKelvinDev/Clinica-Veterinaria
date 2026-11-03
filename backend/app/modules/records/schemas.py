from datetime import date, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=20000)]
Reason = Annotated[str, Field(min_length=3, max_length=500)]


class Correction(BaseModel):
    """Corrigir nunca altera o registro anterior: cria outro que o substitui."""

    supersedes_id: UUID | None = None
    correction_reason: Reason | None = None

    @model_validator(mode="after")
    def reason_with_correction(self) -> Self:
        if (self.supersedes_id is None) != (self.correction_reason is None):
            raise ValueError("Informe o motivo somente ao corrigir um registro")
        return self


class RecordEntryCreate(Correction):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    location: str | None = Field(default=None, min_length=1, max_length=200)
    complaint: Text
    general_state: Text
    findings: Text | None = None
    presumptive_diagnosis: Text
    conclusive_diagnosis: Text | None = None
    procedures: Text | None = None
    prescription: Text | None = None
    follow_up: str | None = Field(default=None, min_length=1, max_length=500)


class RecordEntryRead(BaseModel):
    id: UUID
    patient_id: UUID
    encounter_id: UUID
    root_id: UUID
    version: int
    supersedes_id: UUID | None
    correction_reason: str | None
    author_id: UUID
    author_name: str
    author_crmv: str
    created_at: datetime
    location: str
    complaint: str
    general_state: str
    findings: str | None
    presumptive_diagnosis: str
    conclusive_diagnosis: str | None
    procedures: str | None
    prescription: str | None
    follow_up: str | None


class WeightCreate(Correction):
    model_config = ConfigDict(extra="forbid")
    weight_grams: int = Field(gt=0, le=5_000_000)


class WeightRead(BaseModel):
    id: UUID
    patient_id: UUID
    weight_grams: int
    supersedes_id: UUID | None
    correction_reason: str | None
    author_id: UUID
    author_name: str
    created_at: datetime


class VaccineCreate(Correction):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    encounter_id: UUID
    vaccine_name: str = Field(min_length=1, max_length=200)
    batch: str = Field(min_length=1, max_length=80)
    manufacturer: str = Field(min_length=1, max_length=200)
    dose: str = Field(min_length=1, max_length=80)
    manufactured_on: date
    expires_on: date
    next_dose_on: date | None = None


class VaccineRead(BaseModel):
    id: UUID
    patient_id: UUID
    encounter_id: UUID
    vaccine_name: str
    batch: str
    manufacturer: str
    dose: str
    manufactured_on: date
    expires_on: date
    next_dose_on: date | None
    supersedes_id: UUID | None
    correction_reason: str | None
    author_id: UUID
    author_name: str
    author_crmv: str
    created_at: datetime


class TimelineEncounter(BaseModel):
    id: UUID
    started_at: datetime
    completed_at: datetime | None
    veterinarian_name: str
    appointment_id: UUID | None


class PatientRecord(BaseModel):
    """Recepção recebe somente os atendimentos; o conteúdo clínico fica vazio."""

    patient_id: UUID
    clinical_access: bool
    encounters: list[TimelineEncounter]
    entries: list[RecordEntryRead]
    weights: list[WeightRead]
    vaccines: list[VaccineRead]
    timezone: Literal["America/Fortaleza"] = "America/Fortaleza"
