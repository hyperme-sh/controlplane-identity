"""Rotation contracts with generated credentials and no external services."""
import secrets
from types import SimpleNamespace
import uuid

import jwt
import pytest
from starlette.requests import Request
from controlplane_identity import configuration, internal_token
from controlplane_identity.security import api_key_exchange_jwt as api, tenant_session_jwt as tenant

@pytest.fixture
def keys():
    return tuple(secrets.token_hex(32) for _ in range(3))


def configure(monkeypatch, values, *, legacy=False):
    attrs = dict(smoke_session_claim='hypermesh_smoke',
        usable_api_key_exchange_secret=lambda: values[0],
        usable_api_keys_internal_token=lambda: values[0])
    if not legacy:
        attrs.update(usable_api_key_exchange_secrets=lambda: values,
            usable_api_keys_internal_tokens=lambda: values)
    monkeypatch.setattr(configuration, '_configured', SimpleNamespace(**attrs))


def mint(kind):
    if kind == 'api':
        return api.mint_api_key_session_jwt(key_record_id=uuid.uuid4(), tenant_id=uuid.uuid4(), scopes=['chat'])
    if kind == 'tenant':
        return tenant.mint_tenant_session_jwt(claims={'sub':'person'}, tenant_id=uuid.uuid4())
    return tenant.mint_host_setup_session(claims={'sub':'person','azp':'hypermesh-host-setup'}, tenant_id=uuid.uuid4())

DECODERS = dict(api=api.try_decode_api_key_session_jwt,
    tenant=tenant.try_decode_tenant_session_jwt, host=tenant.try_decode_host_setup_session)

@pytest.mark.parametrize('kind', DECODERS)
def test_previous_verifies_only_while_configured(monkeypatch, keys, kind):
    current, previous, unknown = keys
    configure(monkeypatch, [previous], legacy=True)
    old = mint(kind)
    configure(monkeypatch, [unknown], legacy=True)
    wrong = mint(kind)
    configure(monkeypatch, [current, previous])
    assert DECODERS[kind](old)
    assert DECODERS[kind](wrong) is None
    fresh = mint(kind)
    # First candidate must sign, even though verification accepts both.
    assert jwt.decode(fresh, current, algorithms=['HS256'], options={'verify_aud':False})
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(fresh, previous, algorithms=['HS256'], options={'verify_aud':False})
    configure(monkeypatch, [current])
    assert DECODERS[kind](old) is None
    assert DECODERS[kind](fresh)


@pytest.mark.parametrize('kind', DECODERS)
def test_empty_current_never_promotes_previous(monkeypatch, keys, kind):
    configure(monkeypatch, ['', keys[1]])
    with pytest.raises(RuntimeError):
        mint(kind)


@pytest.mark.parametrize('kind', DECODERS)
def test_legacy_settings_and_cross_purpose_refusal(monkeypatch, keys, kind):
    configure(monkeypatch, [keys[0]], legacy=True)
    token = mint(kind)
    assert DECODERS[kind](token)
    for other, decoder in DECODERS.items():
        if other != kind:
            assert decoder(token) is None


def test_internal_tokens_compare_all_candidates(monkeypatch, keys):
    current, previous, unknown = keys
    original = internal_token.hmac.compare_digest
    compared=[]
    def compare(a,b):
        compared.append(b)
        return original(a,b)
    monkeypatch.setattr(internal_token.hmac, 'compare_digest', compare)
    for token, expected in [(current,True),(previous,True),(unknown,False),('',False),(None,False)]:
        compared.clear()
        assert internal_token.internal_token_matches_any(token, [current, '', None, previous]) is expected
        assert compared == [current.encode(), previous.encode()]
    request=Request({'type':'http','headers':[(b'x-internal-token',previous.encode())]})
    assert internal_token.request_has_internal_token(request, [current,previous])
    assert not internal_token.request_has_internal_token(request, current)
    assert internal_token.request_has_internal_token(request, previous)


def test_internal_settings_fallback_and_order(monkeypatch, keys):
    configure(monkeypatch, keys[:2])
    assert configuration.api_keys_internal_tokens() == keys[:2]
    configure(monkeypatch, [keys[0]], legacy=True)
    assert configuration.api_keys_internal_tokens() == (keys[0],)
