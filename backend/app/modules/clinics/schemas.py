from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.clinics.models import Role


class ClinicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    clinic_id: UUID
    name: str
    role: Role
    active: bool
    crmv: str | None
    crmv_state: str | None
    created_at: datetime
    updated_at: datetime


class IdentityRead(BaseModel):
    user: UserRead
    clinic: ClinicRead


class ClinicUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: Role | None = None
    active: bool | None = None
    crmv: str | None = Field(default=None, min_length=1, max_length=30)
    crmv_state: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("crmv_state", mode="before")
    @classmethod
    def normalize_state(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_non_null_fields(self) -> Self:
        for name in {"name", "role", "active"} & self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} não pode ser nulo")
        if not self.model_fields_set:
            raise ValueError("Informe pelo menos um campo para alterar")
        return self
