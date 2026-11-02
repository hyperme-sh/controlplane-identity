"""The distribution must work without a monorepo or legacy API package."""
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import uuid


def test_public_modules_import_without_legacy_packages():
    contract = json.loads((Path(__file__).parents[1] / 'contracts/identity.json').read_text())
    for name in contract['modules']:
        if name.startswith('controlplane_identity'):
            importlib.import_module(name)
    assert not any(name == 'api' or name.startswith(('api.', 'hypermesh_service')) for name in sys.modules)


def test_session_purpose_and_permissions(monkeypatch):
    from controlplane_identity import configuration
    from controlplane_identity.internal_token import internal_token_matches
    from controlplane_identity.person_bind import can_checkout_from_claims
    from controlplane_identity.security.tenant_session_jwt import (
        mint_host_setup_session, try_decode_host_setup_session, try_decode_tenant_session_jwt,
    )
    # Restore the module's original configuration after this test.
    monkeypatch.setattr(configuration, '_configured', SimpleNamespace(
        usable_api_key_exchange_secret=lambda: 'isolated-wheel-test-signing-secret-32-chars'))
    assert internal_token_matches('secret', 'secret')
    assert not internal_token_matches('secret', 'different')
    assert can_checkout_from_claims({'realm_access': {'roles': ['renter']}})
    tenant = uuid.uuid4()
    token = mint_host_setup_session(claims={'azp': 'hypermesh-host-setup', 'sub': 'host-user'}, tenant_id=tenant)
    assert try_decode_host_setup_session(token)['purpose'] == 'host_setup'
    assert try_decode_tenant_session_jwt(token) is None
