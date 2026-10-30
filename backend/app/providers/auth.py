from typing import Protocol
from uuid import UUID

import httpx

from app.core.errors import AuthenticationRequired, ServiceUnavailable


class AuthProvider(Protocol):
    def verify(self, token: str) -> UUID: ...


class SupabaseAuthProvider:
    def __init__(self, url: str, key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.url = url.rstrip("/")
        self.key = key
        self.transport = transport

    def verify(self, token: str) -> UUID:
        if not self.url or not self.key:
            raise ServiceUnavailable("A autenticação ainda não está configurada.")
        try:
            with httpx.Client(timeout=5, transport=self.transport) as client:
                response = client.get(
                    f"{self.url}/auth/v1/user",
                    headers={"apikey": self.key, "Authorization": f"Bearer {token}"},
                )
        except httpx.RequestError:
            raise ServiceUnavailable("Não foi possível verificar a sessão.") from None
        if response.status_code in {401, 403}:
            raise AuthenticationRequired("Sessão inválida ou expirada. Entre novamente.")
        if response.status_code != 200:
            raise ServiceUnavailable("Não foi possível verificar a sessão.")
        try:
            body = response.json()
            if not isinstance(body, dict) or body.get("is_anonymous") is True:
                raise ValueError
            return UUID(body["id"])
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ServiceUnavailable(
                "O serviço de autenticação retornou uma resposta inválida."
            ) from None
