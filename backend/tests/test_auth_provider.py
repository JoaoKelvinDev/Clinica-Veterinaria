from uuid import uuid4

import httpx
import pytest

from app.core.errors import AuthenticationRequired, ServiceUnavailable
from app.providers.auth import SupabaseAuthProvider


def test_supabase_validates_token_with_auth_server() -> None:
    identity = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/v1/user"
        assert request.headers["Authorization"] == "Bearer fictitious-token"
        return httpx.Response(200, json={"id": str(identity), "user_metadata": {"role": "admin"}})

    provider = SupabaseAuthProvider(
        "http://auth.test", "fictitious-key", httpx.MockTransport(handler)
    )
    assert provider.verify("fictitious-token") == identity


@pytest.mark.parametrize("status", [401, 403])
def test_invalid_tokens_are_rejected(status: int) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(status))
    with pytest.raises(AuthenticationRequired):
        SupabaseAuthProvider("http://auth.test", "fictitious-key", transport).verify("invalid")


@pytest.mark.parametrize("body", [{"id": "bad"}, [], {"id": str(uuid4()), "is_anonymous": True}])
def test_malformed_or_anonymous_identity_is_rejected(body: object) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=body))
    with pytest.raises(ServiceUnavailable):
        SupabaseAuthProvider("http://auth.test", "fictitious-key", transport).verify("invalid")


def test_auth_server_failure_does_not_allow_access() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    with pytest.raises(ServiceUnavailable):
        SupabaseAuthProvider("http://auth.test", "fictitious-key", transport).verify("invalid")
