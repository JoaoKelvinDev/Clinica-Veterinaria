from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.tutors.schemas import TutorRead


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    species: str = Field(min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    sex: Literal["male", "female", "unknown"] = "unknown"
    neutered: bool | None = None
    birth_date: date | None = None
    estimated_age_months: int | None = Field(default=None, ge=0)
    coat: str | None = Field(default=None, max_length=120)
    microchip: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)


class PatientUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    species: str | None = Field(default=None, min_length=1, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    sex: Literal["male", "female", "unknown"] | None = None
    neutered: bool | None = None
    birth_date: date | None = None
    estimated_age_months: int | None = Field(default=None, ge=0)
    coat: str | None = Field(default=None, max_length=120)
    microchip: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("Informe os campos que deseja alterar")
        for name in {"name", "species", "sex"} & self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} não pode ser nulo")
        return self


class PatientRead(PatientCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    clinic_id: UUID


class PatientPage(BaseModel):
    items: list[PatientRead]
    total: int


class TutorLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tutor_id: UUID
    is_primary: bool = False


class TutorLinkRead(BaseModel):
    id: UUID
    is_primary: bool
    tutor: TutorRead
