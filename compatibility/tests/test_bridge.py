import time
import uuid
from types import SimpleNamespace

import jwt
import pytest

from controlplane_legacy_auth_bridge import (
    try_decode_api_key_session_jwt as api,
    try_decode_host_setup_session as setup,
    try_decode_tenant_session_jwt as tenant,
)
from controlplane_identity import configuration
from controlplane_identity.configuration import settings

SECRET = "test-legacy-auth-bridge-only-" + "x" * 40
TENANT = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(configuration, "_configured", SimpleNamespace(usable_api_key_exchange_secret=lambda: SECRET))
    monkeypatch.setenv("CONTROLPLANE_ACCEPT_LEGACY_AUTH", "1")


def claims(kind="tenant-session", canonical=False):
    namespace = "spanopticon" if canonical else "panopticon"
    value = {"iss": f"https://{namespace}.internal/{kind}", "sub": "person-123",
             "exp": int(time.time()) + 300, "tenant_id": TENANT,
             f"https://{namespace}.dev/tenant_id": TENANT}
    if kind == "host-setup":
        value.update(aud="hypermesh-host-setup", azp="hypermesh-host-setup", purpose="host_setup")
    else:
        value[f"{namespace}_auth"] = "tenant_session" if kind == "tenant-session" else "api_key"
        value.update(azp="controlplane-frontend" if kind == "tenant-session" else "controlplane-api-key",
                     purpose="service" if kind == "api-key" else "interactive")
    return value


def token(value, secret=SECRET):
    return jwt.encode(value, secret, algorithm="HS256")


@pytest.mark.parametrize("kind,decoder", [("tenant-session", tenant), ("api-key", api), ("host-setup", setup)])
def test_explicit_opt_in_and_canonical_still_works(monkeypatch, kind, decoder):
    monkeypatch.delenv("CONTROLPLANE_ACCEPT_LEGACY_AUTH")
    assert decoder(token(claims(kind))) is None
    assert decoder(token(claims(kind, canonical=True))) is not None
    monkeypatch.setenv("CONTROLPLANE_ACCEPT_LEGACY_AUTH", "true")
    assert decoder(token(claims(kind))) is None
    monkeypatch.setenv("CONTROLPLANE_ACCEPT_LEGACY_AUTH", "1")
    decoded = decoder(token(claims(kind)))
    assert decoded["https://spanopticon.dev/tenant_id"] == TENANT
    assert decoded["iss"] == claims(kind)["iss"]


@pytest.mark.parametrize("kind,decoder", [("tenant-session", tenant), ("api-key", api), ("host-setup", setup)])
@pytest.mark.parametrize("mutation", ["signature", "expired", "issuer", "missing_exp", "missing_sub", "tenant", "conflict", "namespace", "audience"])
def test_rejects_invalid_credentials(kind, decoder, mutation):
    value = claims(kind)
    if mutation == "expired": value["exp"] = int(time.time()) - 1
    if mutation == "issuer": value["iss"] += "/other"
    if mutation == "missing_exp": value.pop("exp")
    if mutation == "missing_sub": value.pop("sub")
    if mutation == "tenant": value["tenant_id"] = "not-a-uuid"
    if mutation == "conflict": value["https://spanopticon.dev/tenant_id"] = str(uuid.uuid4())
    if mutation == "namespace": value["spanopticon_auth"] = "tenant_session"
    if mutation == "audience": value["aud"] = "other-client"
    assert decoder(token(value, "wrong-" + SECRET if mutation == "signature" else SECRET)) is None


@pytest.mark.parametrize("kind,expected", [("tenant-session", tenant), ("api-key", api), ("host-setup", setup)])
def test_credential_kinds_cannot_cross(kind, expected):
    signed = token(claims(kind))
    for decoder in (tenant, api, setup):
        assert (decoder(signed) is not None) == (decoder is expected)


@pytest.mark.parametrize("field,value", [("azp", "hypermesh-host-setup"), ("purpose", "host_setup"), ("panopticon_auth", "api_key")])
def test_tenant_rejects_setup_and_wrong_marker(field, value):
    payload = claims()
    payload[field] = value
    assert tenant(token(payload)) is None


@pytest.mark.parametrize("field,value", [("realm_access", {"roles": ["admin"]}), ("permissions", ["admin"]), ("groups", ["admin"]), ("azp", "controlplane-frontend"), ("purpose", "service")])
def test_setup_cannot_carry_grants(field, value):
    payload = claims("host-setup")
    payload[field] = value
    assert setup(token(payload)) is None


def test_preserves_authority_and_classification():
    value = claims()
    value.update(realm_access={"roles": ["auditor"]}, permissions=["existing"], amr=["pwd"],
                 account_type="service", smoke_session=True)
    decoded = tenant(token(value))
    for key, item in value.items():
        assert decoded[key] == item
    assert set(decoded) - set(value) == {"spanopticon_auth", "https://spanopticon.dev/tenant_id"}


def test_missing_usable_secret(monkeypatch):
    monkeypatch.setattr(configuration, "_configured", SimpleNamespace(usable_api_key_exchange_secret=lambda: None))
    assert tenant(token(claims())) is None
