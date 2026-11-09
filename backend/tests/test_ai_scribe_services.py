from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core.errors import AccessDenied, ServiceUnavailable
from app.modules.ai_scribe.repositories import DraftRepository
from app.modules.ai_scribe.schemas import DraftGenerate
from app.modules.ai_scribe.services import ScribeService
from app.modules.clinics.models import Role, User
from app.modules.records.services import RecordService
from app.providers.llm import MockLLMProvider
from app.providers.speech_to_text import MockSpeechToTextProvider


def actor(role: Role = Role.VETERINARIAN) -> User:
    return User(id=uuid4(), clinic_id=uuid4(), role=role, active=True, crmv="1", crmv_state="PI")


@pytest.mark.parametrize(
    "output",
    [
        None,
        "JSON inválido",
        {"uncertainties": [], "extra": "x"},
        {"complaint": 10, "uncertainties": []},
    ],
)
def test_invalid_llm_output_has_no_partial_draft_or_record(output: object) -> None:
    drafts, records = Mock(spec=DraftRepository), Mock(spec=RecordService)
    records.scheduling = Mock()
    llm = MockLLMProvider()
    llm_mock = Mock(wraps=llm)
    llm_mock.generate.return_value = output
    service = ScribeService(drafts, records, llm_mock, MockSpeechToTextProvider())
    with pytest.raises(ServiceUnavailable):
        service.generate(actor(), uuid4(), DraftGenerate(transcript="Relato fictício"))
    drafts.save.assert_not_called()
    records.add_entry.assert_not_called()
    records.audit_scribe.assert_not_called()


def test_provider_exception_does_not_expose_transcript_in_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    drafts, records = Mock(spec=DraftRepository), Mock(spec=RecordService)
    records.scheduling = Mock()
    llm = Mock()
    llm.generate.side_effect = RuntimeError("conteúdo sensível fictício")
    service = ScribeService(drafts, records, llm, MockSpeechToTextProvider())
    with pytest.raises(ServiceUnavailable) as error:
        service.generate(actor(), uuid4(), DraftGenerate(transcript="conteúdo sensível fictício"))
    assert "conteúdo sensível" not in caplog.text
    assert "conteúdo sensível" not in str(error.value)
    drafts.save.assert_not_called()


@pytest.mark.parametrize("role", [Role.ADMIN, Role.ASSISTANT, Role.RECEPTION])
def test_non_veterinarian_cannot_reach_generation_provider(role: Role) -> None:
    drafts, records, llm, stt = Mock(spec=DraftRepository), Mock(spec=RecordService), Mock(), Mock()
    with pytest.raises(AccessDenied):
        ScribeService(drafts, records, llm, stt).generate(
            actor(role), uuid4(), DraftGenerate(source="mock_audio", sample_id="consultation")
        )
    llm.generate.assert_not_called()
    stt.transcribe.assert_not_called()
    drafts.save.assert_not_called()
