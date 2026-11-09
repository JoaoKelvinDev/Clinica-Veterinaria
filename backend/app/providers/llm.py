"""Contrato de geração; o MOCK copia campos rotulados, sem interpretação clínica."""

import logging
from typing import Protocol

FIELD_LABELS = {
    "Relato do responsável": "complaint",
    "Estado geral e parâmetros": "general_state",
    "Achados do histórico e dos exames": "findings",
    "Diagnóstico presuntivo": "presumptive_diagnosis",
    "Diagnóstico conclusivo": "conclusive_diagnosis",
    "Procedimentos realizados": "procedures",
    "Prescrição": "prescription",
    "Retorno sugerido": "follow_up",
}


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, transcript: str, *, prompt: str) -> object: ...


class MockLLMProvider:
    name = "mock"
    model = "mock-llm-v1"

    def generate(self, transcript: str, *, prompt: str) -> object:
        logging.getLogger(__name__).info("MOCK LLM: organização por rótulos, sem IA real")
        content: dict[str, object] = dict.fromkeys(FIELD_LABELS.values())
        unlabelled: list[str] = []
        for line in transcript.splitlines():
            label, separator, value = line.partition(":")
            field = FIELD_LABELS.get(label.strip())
            if separator and field and value.strip():
                previous = content[field]
                content[field] = f"{previous}\n{value.strip()}" if previous else value.strip()
            elif line.strip():
                unlabelled.append(line.strip())
        if unlabelled:
            previous = content["complaint"]
            narrative = "\n".join(unlabelled)
            content["complaint"] = f"{previous}\n{narrative}" if previous else narrative
        content["uncertainties"] = [
            "MOCK: somente os rótulos reconhecidos são organizados; revise a transcrição inteira."
        ]
        return content
