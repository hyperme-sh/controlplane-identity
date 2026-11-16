"""Actual JWT mint/verify and task/thread context boundaries; no remote service."""
import asyncio
from types import SimpleNamespace
import uuid
import jwt
import pytest
from controlplane_identity import configuration, nightly
from controlplane_identity.security import tenant_session_jwt as tenant
from controlplane_identity.account_lifecycle import offline_gateway_verification

SUB='11111111-1111-4111-8111-111111111111';TENANT='22222222-2222-4222-8222-222222222222'
SECRET='unit-native-identity-secret-32-characters'
BINDING=dict(version=1,owner='auth',run='123-1-portal-device-transfer',generation='a'*64,
             operation='33333333-3333-4333-8333-333333333333',scope=dict(suite='portal-device-transfer',subject=SUB,tenant=TENANT))
CLAIMS=dict(sub=SUB,nightly_run={k:BINDING[k] for k in ('run','generation')})

@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(configuration,'_configured',SimpleNamespace(usable_api_key_exchange_secret=lambda:SECRET,smoke_session_claim='smoke_session'))
    monkeypatch.setattr(nightly,'_subjects',frozenset({SUB}))


def test_actual_mint_preserves_run_and_rejects_cross_tenant_or_successor():
    with nightly.admitted_run(BINDING):
        token=tenant.mint_tenant_session_jwt(claims=CLAIMS,tenant_id=uuid.UUID(TENANT))
        assert tenant.try_decode_tenant_session_jwt(token)['nightly_run']==CLAIMS['nightly_run']
        with pytest.raises(jwt.InvalidTokenError):tenant.mint_tenant_session_jwt(claims=CLAIMS,tenant_id=uuid.uuid4())
    assert tenant.try_decode_tenant_session_jwt(token) is None
    with nightly.admitted_run(BINDING|{'run':'124-1-portal-device-transfer'}):
        assert tenant.try_decode_tenant_session_jwt(token) is None
    with offline_gateway_verification():assert tenant.try_decode_tenant_session_jwt(token) is None


def test_legacy_fixture_and_unrelated_sender_cannot_bypass_but_unrelated_unbound_works():
    with pytest.raises(jwt.InvalidTokenError):nightly.require_original_run({'sub':SUB})
    nightly.require_original_run({'sub':'unrelated'})
    with nightly.admitted_run(BINDING):
        for claims in ({'sub':SUB},{'sub':'unrelated'},CLAIMS|{'sub':'unrelated'}):
            with pytest.raises(jwt.InvalidTokenError):nightly.require_original_run(claims)
    token=tenant.mint_tenant_session_jwt(claims={'sub':'unrelated'},tenant_id=uuid.UUID(TENANT))
    assert tenant.try_decode_tenant_session_jwt(token)['sub']=='unrelated'


@pytest.mark.asyncio
async def test_detached_context_closes_and_native_thread_validation_preserves_binding():
    gate=asyncio.Event()
    async def delayed():
        await gate.wait()
        with pytest.raises(jwt.InvalidTokenError):nightly.require_original_run(CLAIMS)
    with nightly.admitted_run(BINDING):
        await asyncio.to_thread(nightly.require_original_run,CLAIMS)
        future=asyncio.create_task(delayed())
    gate.set();await future
