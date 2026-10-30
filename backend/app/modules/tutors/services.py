from datetime import UTC, datetime
from uuid import UUID

import phonenumbers
from sqlalchemy.orm import Session

from app.core.errors import InvalidData, ResourceNotFound
from app.core.permissions import require_registry_writer
from app.core.repositories import ClinicContext
from app.modules.clinics.models import User
from app.modules.tutors.models import Tutor
from app.modules.tutors.repositories import TutorRepository
from app.modules.tutors.schemas import ConsentInput, TutorCreate, TutorPage, TutorRead, TutorUpdate


def normalize_phone(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    try:
        parsed = phonenumbers.parse(value, "BR")
        if parsed.extension or not phonenumbers.is_valid_number(parsed):
            raise ValueError
    except (phonenumbers.NumberParseException, ValueError):
        raise InvalidData("Informe um telefone válido com DDD ou código internacional.") from None
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class TutorService:
    def __init__(self, repository: TutorRepository) -> None:
        self.repository = repository

    @classmethod
    def for_clinic(cls, session: Session, context: ClinicContext) -> "TutorService":
        return cls(TutorRepository(session, context))

    def get(self, tutor_id: UUID, *, include_archived: bool = False) -> Tutor:
        tutor = self.repository.get(tutor_id, include_archived=include_archived)
        if tutor is None:
            raise ResourceNotFound("Tutor não encontrado.")
        return tutor

    def list(self, search: str, limit: int, offset: int) -> TutorPage:
        items, total = self.repository.list(search.strip(), limit, offset)
        return TutorPage(items=[TutorRead.model_validate(item) for item in items], total=total)

    def _locked(self, tutor_id: UUID) -> Tutor:
        tutor = self.repository.locked(tutor_id)
        if tutor is None:
            raise ResourceNotFound("Tutor não encontrado.")
        return tutor

    def create(self, actor: User, values: TutorCreate) -> Tutor:
        require_registry_writer(actor)
        tutor = Tutor(
            clinic_id=self.repository.context.clinic_id,
            name=values.name,
            phone=normalize_phone(values.phone),
            document=values.document or None,
            address=values.address or None,
            whatsapp_opt_in=False,
        )
        if values.whatsapp_consent is not None:
            self._apply_consent(tutor, values.whatsapp_consent)
        self.repository.save(tutor)
        return tutor

    def update(self, actor: User, tutor_id: UUID, changes: TutorUpdate) -> Tutor:
        require_registry_writer(actor)
        tutor = self._locked(tutor_id)
        for field in changes.model_fields_set:
            value = getattr(changes, field)
            if field == "phone":
                value = normalize_phone(changes.phone)
                if value != tutor.phone and tutor.whatsapp_opt_in:
                    self._apply_consent(tutor, ConsentInput(granted=False))
            setattr(tutor, field, value or None)
        self.repository.save(tutor)
        return tutor

    def consent(self, actor: User, tutor_id: UUID, values: ConsentInput) -> Tutor:
        require_registry_writer(actor)
        tutor = self._locked(tutor_id)
        self._apply_consent(tutor, values)
        self.repository.save(tutor)
        return tutor

    def _apply_consent(self, tutor: Tutor, values: ConsentInput) -> None:
        if values.granted and not tutor.phone:
            raise InvalidData("Cadastre um telefone antes de registrar a autorização de WhatsApp.")
        tutor.whatsapp_opt_in = values.granted
        if values.granted:
            tutor.whatsapp_opt_in_at = datetime.now(UTC)
            tutor.whatsapp_opt_in_source = values.source
        else:
            tutor.whatsapp_opt_out_at = datetime.now(UTC)

    def archive(self, actor: User, tutor_id: UUID) -> None:
        require_registry_writer(actor)
        tutor = self._locked(tutor_id)
        tutor.deleted_at = datetime.now(UTC)
        self._apply_consent(tutor, ConsentInput(granted=False))
        self.repository.save(tutor)
