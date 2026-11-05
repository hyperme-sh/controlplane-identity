"""Purpose-bound lifecycle authority stays default-off and fails closed."""

import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import jwt
import pytest

from controlplane_identity import account_lifecycle as lifecycle
from controlplane_identity.security.keycloak_jwt import KeycloakJWTValidator


@pytest.fixture
def authority(monkeypatch):
    monkeypatch.setenv("ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED", "true")
    monkeypatch.setenv("ACCOUNT_CLOSURE_GUARD_TOKEN", "r" * 32)
    monkeypatch.setenv("ACCOUNT_CLOSURE_OPERATIONS_TOKEN", "w" * 32)
    monkeypatch.setenv("ACCOUNT_CLOSURE_GUARD_URL", "https://users.example")


def test_default_off_and_separate_reader_writer_tokens(monkeypatch, authority):
    reader = {"X-Account-Lifecycle-Token": "r" * 32}
    writer = {"X-Account-Lifecycle-Token": "w" * 32}
    assert lifecycle.authorized_call(reader)
    assert not lifecycle.authorized_call(writer)
    assert lifecycle.authorized_call(writer, mutation=True)
    assert not lifecycle.authorized_call(reader, mutation=True)
    monkeypatch.delenv("ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED")
    assert not lifecycle.authorized_call(reader)
    lifecycle.require_open_account({"sub": "person"})


@pytest.mark.parametrize(
    "payload", [None, {}, {"blocked": True}, {"blocked": 0}, {"blocked": "false"}, []]
)
def test_guard_rejects_unknown_or_retired_reply(monkeypatch, authority, payload):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        lifecycle.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=payload)
            ),
            **kwargs,
        ),
    )
    with pytest.raises(jwt.InvalidTokenError):
        lifecycle.require_open_account({"sub": "person"})


def test_open_account_uses_exact_subject_and_canonical_tenant(monkeypatch, authority):
    original = httpx.AsyncClient
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"blocked": False})

    monkeypatch.setattr(
        lifecycle.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    tenant = str(uuid.uuid4())
    lifecycle.require_open_account(
        {"sub": " exact ", "https://spanopticon.dev/tenant_id": tenant}
    )
    import json

    assert json.loads(requests[0].content) == {
        "subject": " exact ",
        "tenant_id": tenant,
    }
    assert requests[0].headers["X-Account-Lifecycle-Token"] == "r" * 32
    assert requests[0].url.path == "/api/v1/internal/account-lifecycle/check"


def test_offline_gateway_context_is_scoped(authority):
    with pytest.raises(ValueError), lifecycle.offline_gateway_verification():
        lifecycle.require_open_account({})
        raise ValueError("owned test")
    with pytest.raises(jwt.InvalidTokenError):
        lifecycle.require_open_account({})


@pytest.mark.parametrize(
    "url",
    [
        "http://users.example",
        "https://user:secret@users.example",
        "https://users.example?q=token",
        "https://users.example/#secret",
    ],
)
def test_production_owner_destination_cannot_embed_credentials(monkeypatch, url):
    monkeypatch.setenv("FASTAPI_ENV", "production")
    monkeypatch.setenv("ACCOUNT_CLOSURE_GUARD_URL", url)
    with pytest.raises(RuntimeError, match="URL unavailable"):
        lifecycle.service_url("ACCOUNT_CLOSURE_GUARD_URL")


def test_digests_bind_subject_and_credential_to_tenant():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert lifecycle.subject_digest(a, "person") != lifecycle.subject_digest(
        b, "person"
    )
    assert lifecycle.key_digest(a, a) != lifecycle.key_digest(b, a)


def test_native_operator_grant_uses_separate_audience_and_current_client_list(
    monkeypatch,
):
    validator = KeycloakJWTValidator(
        jwks_url="https://issuer.example/jwks",
        issuer="https://issuer.example",
        client_id="controlplane-frontend",
    )
    validator._jwks_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key="test")
    )
    claims = {
        "azp": "closure-cli",
        "sub": "operator",
        "realm_access": {"roles": ["account:close"]},
    }
    decode = Mock(return_value=claims)
    monkeypatch.setattr(jwt, "decode", decode)
    assert (
        validator.validate_closure_operator_sync(
            "fixture", client_ids=frozenset({"closure-cli"})
        )
        == claims
    )
    assert decode.call_args.kwargs["audience"] == "spanopticon-account-closure"
    assert decode.call_args.kwargs["algorithms"] == ["RS256"]
    claims["spanopticon_auth"] = "api_key"
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate_closure_operator_sync(
            "fixture", client_ids=frozenset({"closure-cli"})
        )


def test_trickling_retirement_authority_has_total_deadline(monkeypatch, authority):
    import asyncio

    original = httpx.AsyncClient
    closed = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(1000):
                await asyncio.sleep(0.005)
                yield b" "

        async def aclose(self):
            closed.append(True)

    monkeypatch.setattr(lifecycle, "_RPC_DEADLINE_SECONDS", 0.03)
    monkeypatch.setattr(
        lifecycle.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, stream=Stream())
            ),
            **kwargs,
        ),
    )
    with pytest.raises(jwt.InvalidTokenError, match="authorization unavailable"):
        lifecycle.require_open_account({"sub": "person"})
    assert closed == [True]


@pytest.mark.parametrize("kind", ["general", "host", "operator"])
async def test_validator_executor_propagates_and_restores_offline_context(
    authority, monkeypatch, kind
):
    validator = KeycloakJWTValidator(
        jwks_url="https://issuer.example/jwks",
        issuer="https://issuer.example",
        client_id="client",
    )

    def validate(_token, **kwargs):
        lifecycle.require_open_account({})
        return {"verified": True}

    monkeypatch.setattr(validator, "validate_sync", validate)
    monkeypatch.setattr(validator, "validate_host_setup_sync", validate)
    monkeypatch.setattr(validator, "validate_closure_operator_sync", validate)

    async def call():
        if kind == "operator":
            return await validator.validate_closure_operator(
                "fixture", client_ids=frozenset({"client"})
            )
        return await (
            validator.validate_host_setup("fixture")
            if kind == "host"
            else validator.validate("fixture")
        )

    with lifecycle.offline_gateway_verification():
        assert await call() == {"verified": True}
    with pytest.raises(jwt.InvalidTokenError):
        await call()


@pytest.mark.parametrize("kind", ["tenant", "host"])
async def test_async_session_entrypoint_checks_healthy_authority_without_blocking(
    authority, monkeypatch, kind
):
    import asyncio

    from controlplane_identity import configuration
    from controlplane_identity.security import tenant_session_jwt as session

    monkeypatch.setattr(
        configuration,
        "_configured",
        SimpleNamespace(
            usable_api_key_exchange_secret=lambda: (
                "async-guard-test-signing-secret-32-chars!!"
            ),
            smoke_session_claim="smoke_session",
        ),
    )
    tenant = uuid.uuid4()
    claims = {
        "sub": "owner",
        "azp": "hypermesh-host-setup" if kind == "host" else "controlplane-frontend",
    }
    token = (
        session.mint_host_setup_session
        if kind == "host"
        else session.mint_tenant_session_jwt
    )(claims=claims, tenant_id=tenant)
    original = httpx.AsyncClient

    loop = asyncio.get_running_loop()
    progress = []

    async def respond(_):
        from concurrent.futures import Future

        served = Future()

        def serve_on_caller_loop():
            progress.append(True)
            served.set_result(None)

        loop.call_soon_threadsafe(serve_on_caller_loop)
        await asyncio.wrap_future(served)
        return httpx.Response(200, json={"blocked": False})

    monkeypatch.setattr(
        lifecycle.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs),
    )
    decode = (
        session.try_decode_host_setup_session_async
        if kind == "host"
        else session.try_decode_tenant_session_jwt_async
    )
    assert (await decode(token))["sub"] == "owner"
    assert progress == [True]
