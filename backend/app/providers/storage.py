"""Armazenamento de arquivos do prontuário atrás de uma interface (AGENTS.md, seção 3)."""

import logging
from typing import Protocol
from urllib.parse import quote

import httpx

from app.core.errors import BusinessConflict, ServiceUnavailable

BUCKET = "vetsys-documents"


class FileStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...


class SupabaseFileStorage:
    """Bucket privado do Supabase Storage local; nunca sobrescreve um objeto."""

    def __init__(
        self, url: str, secret_key: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.url = url.rstrip("/")
        self.secret_key = secret_key
        self.transport = transport

    def _client(self) -> httpx.Client:
        if not self.url or not self.secret_key:
            raise ServiceUnavailable("O armazenamento de arquivos ainda não está configurado.")
        return httpx.Client(
            base_url=f"{self.url}/storage/v1",
            headers={"apikey": self.secret_key, "Authorization": f"Bearer {self.secret_key}"},
            timeout=30,
            transport=self.transport,
        )

    def put(self, key: str, content: bytes, content_type: str) -> None:
        try:
            with self._client() as client:
                response = client.post(
                    f"/object/{BUCKET}/{quote(key)}",
                    content=content,
                    headers={"Content-Type": content_type, "x-upsert": "false"},
                )
        except httpx.RequestError:
            raise ServiceUnavailable("Não foi possível guardar o arquivo.") from None
        if response.status_code == 409:
            raise BusinessConflict("Já existe um arquivo com este identificador.")
        if response.status_code not in {200, 201}:
            raise ServiceUnavailable("Não foi possível guardar o arquivo.")

    def get(self, key: str) -> bytes:
        try:
            with self._client() as client:
                response = client.get(f"/object/{BUCKET}/{quote(key)}")
        except httpx.RequestError:
            raise ServiceUnavailable("Não foi possível abrir o arquivo.") from None
        if response.status_code != 200:
            raise ServiceUnavailable("Não foi possível abrir o arquivo.")
        return response.content


class MemoryFileStorage:
    """Implementação simulada para testes; identificada como MOCK nos logs."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def put(self, key: str, content: bytes, content_type: str) -> None:
        logging.getLogger(__name__).info("MOCK file storage: put")
        if key in self.objects:
            raise BusinessConflict("Já existe um arquivo com este identificador.")
        self.objects[key] = (content, content_type)

    def get(self, key: str) -> bytes:
        logging.getLogger(__name__).info("MOCK file storage: get")
        if key not in self.objects:
            raise ServiceUnavailable("Não foi possível abrir o arquivo.")
        return self.objects[key][0]
