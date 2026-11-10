from datetime import datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.patients.schemas import PatientRead, TutorLinkRead
from app.modules.records.schemas import PatientRecord
from app.modules.tutors.schemas import TutorRead

Contact = Annotated[str, Field(min_length=3, max_length=500)]


class ExportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    tutor_id: UUID
    professional_address: Contact
    professional_phone: str = Field(min_length=8, max_length=40)
    professional_email: str = Field(
        min_length=5, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    )
    establishment_legal_name: str | None = Field(default=None, min_length=1, max_length=200)
    establishment_cnpj: str | None = Field(default=None, min_length=14, max_length=18)
    establishment_crmv: str | None = Field(default=None, min_length=3, max_length=40)
    acknowledge_unsigned: bool = Field(strict=True)

    @model_validator(mode="after")
    def complete_emission(self) -> Self:
        if not self.acknowledge_unsigned:
            raise ValueError("Confirme a necessidade de assinatura e entrega manuais.")
        fields = (self.establishment_legal_name, self.establishment_cnpj, self.establishment_crmv)
        if any(value is not None for value in fields) and not all(fields):
            raise ValueError("Complete os dados do estabelecimento ou remova todos.")
        return self


class Attachment(BaseModel):
    document_id: UUID
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str


class ExportSnapshot(BaseModel):
    export_id: UUID
    generated_at: datetime
    clinic_name: str
    patient: PatientRead
    tutor: TutorRead
    author_name: str
    author_crmv: str
    emission: ExportCreate
    record: PatientRecord


class ExportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    patient_id: UUID
    author_name: str
    author_crmv: str
    tutor_name: str
    created_at: datetime
    sha256: str
    size_bytes: int
    attachment_count: int
    missing_file_count: int


class ExportPage(BaseModel):
    items: list[ExportRead]
    total: int


class ExportOptions(BaseModel):
    clinic_name: str
    patient_name: str
    tutors: list[TutorLinkRead]
