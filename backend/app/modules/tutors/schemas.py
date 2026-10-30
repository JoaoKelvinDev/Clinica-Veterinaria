from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    granted: bool
    source: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_source(self) -> Self:
        if self.granted and not self.source:
            raise ValueError("Informe a origem da autorização")
        return self


class TutorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    document: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    whatsapp_consent: ConsentInput | None = None


class TutorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    document: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set or ("name" in self.model_fields_set and self.name is None):
            raise ValueError("Informe os campos que deseja alterar")
        return self


class TutorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    clinic_id: UUID
    name: str
    phone: str | None
    document: str | None
    address: str | None
    whatsapp_opt_in: bool
    whatsapp_opt_in_at: datetime | None
    whatsapp_opt_in_source: str | None
    whatsapp_opt_out_at: datetime | None
    deleted_at: datetime | None


class TutorPage(BaseModel):
    items: list[TutorRead]
    total: int
