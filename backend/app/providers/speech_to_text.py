"""Transcrição simulada: aceita apenas o identificador de um exemplo fictício."""

import logging
from typing import Protocol

MOCK_TRANSCRIPT = (
    "Relato do responsável: Tutor fictício relata redução de apetite desde ontem.\n"
    "Achados do histórico e dos exames: Peso informado na consulta fictícia: 12 kg."
)


class SpeechToTextProvider(Protocol):
    name: str
    model: str

    def transcribe(self, sample_id: str) -> str: ...


class MockSpeechToTextProvider:
    name = "mock"
    model = "mock-stt-v1"

    def transcribe(self, sample_id: str) -> str:
        if sample_id != "consultation":
            raise ValueError("Exemplo MOCK desconhecido")
        logging.getLogger(__name__).info("MOCK STT: transcrição fictícia, sem áudio real")
        return MOCK_TRANSCRIPT
