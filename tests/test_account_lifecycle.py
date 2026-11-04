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
    monkeypatch.setenv('ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED', 'true')
    monkeypatch.setenv('ACCOUNT_CLOSURE_GUARD_TOKEN', 'r' * 32)
    monkeypatch.setenv('ACCOUNT_CLOSURE_OPERATIONS_TOKEN', 'w' * 32)
    monkeypatch.setenv('ACCOUNT_CLOSURE_GUARD_URL', 'https://users.example')


def test_default_off_and_separate_reader_writer_tokens(monkeypatch, authority):
    reader={'X-Account-Lifecycle-Token':'r'*32}
    writer={'X-Account-Lifecycle-Token':'w'*32}
    assert lifecycle.authorized_call(reader)
    assert not lifecycle.authorized_call(writer)
    assert lifecycle.authorized_call(writer, mutation=True)
    assert not lifecycle.authorized_call(reader, mutation=True)
    monkeypatch.delenv('ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED')
    assert not lifecycle.authorized_call(reader)
    lifecycle.require_open_account({'sub':'person'})


@pytest.mark.parametrize('payload', [None, {}, {'blocked':True}, {'blocked':0}, {'blocked':'false'}, []])
def test_guard_rejects_unknown_or_retired_reply(monkeypatch, authority, payload):
    original=httpx.Client
    monkeypatch.setattr(lifecycle.httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload)), **kwargs))
    with pytest.raises(jwt.InvalidTokenError):
        lifecycle.require_open_account({'sub':'person'})


def test_open_account_uses_exact_subject_and_canonical_tenant(monkeypatch, authority):
    original=httpx.Client
    requests=[]
    def respond(request):
        requests.append(request)
        return httpx.Response(200,json={'blocked':False})
    monkeypatch.setattr(lifecycle.httpx, 'Client', lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    tenant=str(uuid.uuid4())
    lifecycle.require_open_account({'sub':' exact ', 'https://spanopticon.dev/tenant_id':tenant})
    import json
    assert json.loads(requests[0].content)=={'subject':' exact ', 'tenant_id':tenant}
    assert requests[0].headers['X-Account-Lifecycle-Token']=='r'*32
    assert requests[0].url.path=='/api/v1/internal/account-lifecycle/check'


def test_offline_gateway_context_is_scoped(authority):
    with pytest.raises(ValueError), lifecycle.offline_gateway_verification():
        lifecycle.require_open_account({})
        raise ValueError('owned test')
    with pytest.raises(jwt.InvalidTokenError):
        lifecycle.require_open_account({})


@pytest.mark.parametrize('url',['http://users.example','https://user:secret@users.example','https://users.example?q=token','https://users.example/#secret'])
def test_production_owner_destination_cannot_embed_credentials(monkeypatch,url):
    monkeypatch.setenv('FASTAPI_ENV','production')
    monkeypatch.setenv('ACCOUNT_CLOSURE_GUARD_URL',url)
    with pytest.raises(RuntimeError,match='URL unavailable'):
        lifecycle.service_url('ACCOUNT_CLOSURE_GUARD_URL')


def test_digests_bind_subject_and_credential_to_tenant():
    a,b=uuid.uuid4(),uuid.uuid4()
    assert lifecycle.subject_digest(a,'person') != lifecycle.subject_digest(b,'person')
    assert lifecycle.key_digest(a,a) != lifecycle.key_digest(b,a)


def test_native_operator_grant_uses_separate_audience_and_current_client_list(monkeypatch):
    validator=KeycloakJWTValidator(jwks_url='https://issuer.example/jwks',issuer='https://issuer.example',client_id='controlplane-frontend')
    validator._jwks_client=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key='test'))
    claims={'azp':'closure-cli','sub':'operator','realm_access':{'roles':['account:close']}}
    decode=Mock(return_value=claims)
    monkeypatch.setattr(jwt,'decode',decode)
    assert validator.validate_closure_operator_sync('fixture',client_ids=frozenset({'closure-cli'}))==claims
    assert decode.call_args.kwargs['audience']=='spanopticon-account-closure'
    assert decode.call_args.kwargs['algorithms']==['RS256']
    claims['spanopticon_auth']='api_key'
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate_closure_operator_sync('fixture',client_ids=frozenset({'closure-cli'}))
