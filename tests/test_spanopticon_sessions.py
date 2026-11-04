"""Canonical session namespaces and purpose separation for the coordinated cutover."""
from types import SimpleNamespace
import uuid

import jwt
import pytest

from controlplane_identity import configuration
from controlplane_identity.security import api_key_exchange_jwt as api_key
from controlplane_identity.security import tenant_session_jwt as tenant_session

SECRET = "isolated-spanopticon-namespace-test-secret-32-chars"


@pytest.mark.parametrize("kind", ["tenant", "api_key"])
def test_canonical_claims_and_purpose_separation(monkeypatch, kind):
    monkeypatch.setattr(configuration, "_configured", SimpleNamespace(
        usable_api_key_exchange_secret=lambda: SECRET,
        smoke_session_claim="smoke_session",
    ))
    tenant = uuid.uuid4()
    if kind == "tenant":
        token = tenant_session.mint_tenant_session_jwt(claims={"sub": "owner"}, tenant_id=tenant)
        decode = tenant_session.try_decode_tenant_session_jwt
        other = api_key.try_decode_api_key_session_jwt
        issuer = "https://spanopticon.internal/tenant-session"
        marker = "tenant_session"
    else:
        token = api_key.mint_api_key_session_jwt(key_record_id=uuid.uuid4(), tenant_id=tenant, scopes=[])
        decode = api_key.try_decode_api_key_session_jwt
        other = tenant_session.try_decode_tenant_session_jwt
        issuer = "https://spanopticon.internal/api-key"
        marker = "api_key"
    claims = decode(token)
    assert claims["iss"] == issuer
    assert claims["spanopticon_auth"] == marker
    assert claims["https://spanopticon.dev/tenant_id"] == str(tenant)
    assert other(token) is None
    claims["iss"] = "https://untrusted.invalid/tenant-session"
    assert decode(jwt.encode(claims, SECRET, algorithm="HS256")) is None
    claims["iss"] = issuer
    claims.pop("spanopticon_auth")
    assert decode(jwt.encode(claims, SECRET, algorithm="HS256")) is None
