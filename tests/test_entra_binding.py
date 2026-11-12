"""Offline account-selector contracts; no token verifier or owner API is replaced."""
from dataclasses import FrozenInstanceError
import pytest
from controlplane_identity.entra_binding import EntraAccountBinding, EntraBindingError

TENANT = '11111111-1111-4111-8111-111111111111'
ACCOUNT = '22222222-2222-4222-8222-222222222222'
APP = '33333333-3333-4333-8333-333333333333'

@pytest.fixture
def config():
    return dict(tenant_id=TENANT, object_id=ACCOUNT, issuer=f'https://login.microsoftonline.com/{TENANT}/v2.0',
                audience=APP, subject='application-specific-subject', broker='startup-entra')

@pytest.fixture
def claims(config):
    return dict(ver='2.0', tid=TENANT, oid=ACCOUNT, iss=config['issuer'], aud=APP, sub=config['subject'])


def test_exact_binding_matches_without_email_or_role(config, claims):
    binding = EntraAccountBinding.from_config(config)
    assert binding.matches_verified_id_token(claims, broker='startup-entra')
    assert binding.matches_verified_id_token({**claims, 'email': 'changed@example.invalid', 'roles': ['member']}, broker='startup-entra')
    assert not binding.matches_verified_id_token({**claims, 'oid': APP, 'email': 'same@example.invalid', 'roles': ['admin']}, broker='startup-entra')


@pytest.mark.parametrize('field', ['ver', 'tid', 'oid', 'iss', 'aud', 'sub'])
@pytest.mark.parametrize('replacement', [None, '', 1, True, [], ['value'], 'different'])
def test_every_immutable_claim_is_required_and_exact(config, claims, field, replacement):
    binding = EntraAccountBinding.from_config(config)
    assert not binding.matches_verified_id_token({**claims, field: replacement}, broker='startup-entra')
    del claims[field]
    assert not binding.matches_verified_id_token(claims, broker='startup-entra')


@pytest.mark.parametrize('broker', ['', 'other', 'Startup-entra', None, ['startup-entra']])
def test_server_broker_must_match(config, claims, broker):
    claims['broker'] = 'startup-entra'
    assert not EntraAccountBinding.from_config(config).matches_verified_id_token(claims, broker=broker)


@pytest.mark.parametrize('value', [None, [], 'unverified-token', 1])
def test_non_object_claims_refuse(config, value):
    assert not EntraAccountBinding.from_config(config).matches_verified_id_token(value, broker='startup-entra')


@pytest.mark.parametrize('field', ['tenant_id', 'object_id', 'issuer', 'audience', 'subject', 'broker'])
def test_closed_config_requires_every_binding(config, field):
    del config[field]
    with pytest.raises(EntraBindingError): EntraAccountBinding.from_config(config)


@pytest.mark.parametrize('field,value', [
    ('tenant_id', None), ('object_id', 'not-a-uuid'), ('audience', 1),
    ('tenant_id', '00000000-0000-0000-0000-000000000000'),
    ('object_id', 'AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA'),
    ('object_id', 'x'*36), ('issuer', 'https://login.microsoftonline.com/common/v2.0'),
    ('issuer', 'https://login.microsoftonline.com/'+TENANT+'/v2.0/'), ('issuer', None),
    ('subject', ''), ('subject', 'private\nsubject'), ('subject', 'x'*257), ('subject', None),
    ('broker', '../broker'), ('broker', ''), ('broker', None),
])
def test_invalid_config_refuses_without_printing_values(config, field, value):
    config[field] = value
    with pytest.raises(EntraBindingError, match='^Entra account binding refused$'):
        EntraAccountBinding.from_config(config)


@pytest.mark.parametrize('extra', ['email', 'private_key', 'roles', 'keycloak_sub'])
def test_extra_fields_do_not_expand_authority(config, extra):
    with pytest.raises(EntraBindingError): EntraAccountBinding.from_config({**config, extra: 'private-sentinel'})


def test_binding_is_immutable_and_repr_does_not_disclose_ids(config):
    binding = EntraAccountBinding.from_config(config)
    config['subject'] = 'changed'
    assert binding.subject == 'application-specific-subject'
    with pytest.raises(FrozenInstanceError): binding.subject = 'changed'
    assert TENANT not in repr(binding) and ACCOUNT not in repr(binding) and binding.subject not in repr(binding)
