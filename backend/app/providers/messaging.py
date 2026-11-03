"""Envio de WhatsApp atrás de uma interface (AGENTS.md, seção 6.5).

Nesta etapa só existe a implementação simulada: nada sai do computador e não há custo.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4


class MessagingProvider(Protocol):
    name: str

    def send(self, phone: str, body: str) -> str:
        """Envia a mensagem e devolve o identificador dado pelo provedor."""
        ...


@dataclass
class MockMessagingProvider:
    """Registra as mensagens em memória e no log como MOCK; não envia nada."""

    name: str = "mock"
    sent: list[tuple[str, str]] = field(default_factory=list)

    def send(self, phone: str, body: str) -> str:
        # Sem telefone nem texto no log: são dados pessoais (AGENTS.md, seção 8.3).
        logging.getLogger(__name__).info(
            "MOCK messaging provider: mensagem registrada, não enviada"
        )
        self.sent.append((phone, body))
        return f"mock-{uuid4()}"
