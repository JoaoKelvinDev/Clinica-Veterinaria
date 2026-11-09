import pytest

from app.modules.ai_scribe.prompts import SYSTEM_PROMPT
from app.modules.ai_scribe.schemas import DraftContent
from app.providers.llm import MockLLMProvider
from app.providers.speech_to_text import MOCK_TRANSCRIPT, MockSpeechToTextProvider


def test_mock_stt_only_returns_fictitious_sample() -> None:
    provider = MockSpeechToTextProvider()
    assert provider.transcribe("consultation") == MOCK_TRANSCRIPT
    with pytest.raises(ValueError):
        provider.transcribe("arquivo-real.wav")


def test_mock_organizes_only_explicit_labels_without_inventing_clinical_fields() -> None:
    result = DraftContent.model_validate(
        MockLLMProvider().generate(
            "Relato do responsável: Relato fictício.\nTexto livre preservado.\n"
            "Prescrição: Conduta já ditada pelo veterinário.",
            prompt=SYSTEM_PROMPT,
        )
    )
    assert result.complaint == "Relato fictício.\nTexto livre preservado."
    assert result.prescription == "Conduta já ditada pelo veterinário."
    assert result.general_state is None
    assert result.presumptive_diagnosis is None
    assert result.conclusive_diagnosis is None
    assert result.uncertainties and "MOCK" in result.uncertainties[0]


def test_prompt_limits_to_transcript_marks_uncertainties_and_requires_human_review() -> None:
    assert "Não invente" in SYSTEM_PROMPT
    assert "incertezas" in SYSTEM_PROMPT
    assert "não sugira condutas" in SYSTEM_PROMPT
    assert "aprovação explícita" in SYSTEM_PROMPT
