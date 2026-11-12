import copy
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from controlplane_identity.startup import (
    InvalidBinding, binding_fingerprint, canonical_binding, fingerprint, load, validate, verify_claims,
)

FIXTURE = Path(__file__).parent / 'fixtures/startup-identity.json'


def mapping():
    return json.loads(FIXTURE.read_bytes())


def claims(config):
    entra = config['binding']['entra']
    return {'iss': config['owner']['broker']['issuer'], 'aud': config['owner']['broker']['audience'],
            'azp': config['owner']['broker']['audience'], 'login_provider': entra['broker'],
            'entra_tenant_id': entra['tenant_id'], 'entra_object_id': entra['object_id'], 'sub': 'opaque-person'}


def test_normalization_snapshots_nested_values_and_separates_grants():
    source = mapping()
    source['binding']['organizations']['fyberlabs']['roles'].reverse()
    result = validate(source)
    assert result == mapping()
    source['binding']['platform_admin']['hyperme.sh'] = True
    source['owner']['profile']['email'] = 'changed@example.invalid'
    assert result == mapping()
    assert result['binding']['platform_admin'] == {'spanopticon': True, 'hyperme.sh': False}
    assert result['binding']['keycloak_admin']['enabled'] is False
    assert fingerprint(result) == fingerprint(validate(result))
    raw = canonical_binding(json.dumps(result['binding']).encode())
    assert raw.endswith(b'\n')
    assert hashlib.sha256(raw).hexdigest() == result['binding_sha256']
    changed = copy.deepcopy(result)
    changed['owner']['profile']['email'] = 'other@example.invalid'
    assert fingerprint(changed) != fingerprint(result)
    assert binding_fingerprint(changed['binding']) == result['binding_sha256']


@pytest.mark.parametrize('scope', [(), ('owner',), ('owner','profile'), ('owner','broker'),
                                  ('binding',), ('binding','entra'), ('binding','platform_admin'),
                                  ('binding','keycloak_admin'), ('binding','organizations'),
                                  ('binding','organizations','fyberlabs')])
def test_closed_fields_at_every_level(scope):
    original = mapping()
    node = original
    for key in scope: node = node[key]
    for key in [*node, 'unexpected']:
        value = copy.deepcopy(original)
        target = value
        for part in scope: target = target[part]
        if key == 'unexpected': target[key] = 'private-sentinel'
        else: del target[key]
        with pytest.raises(InvalidBinding, match='^Startup identity configuration refused$'):
            validate(value)


@pytest.mark.parametrize('path,value', [
    (('schema_version',), True), (('schema_version',), 2), (('binding_sha256',), '0'*64),
    (('owner','tenant_id'), '00000000-0000-0000-0000-000000000000'),
    (('owner','network_id'), ''), (('owner','network_id'), 'x'*256),
    (('owner','profile','email'), 'missing-at'), (('owner','profile','email'), 'a@b\x00'),
    (('owner','profile','email'), 'a'*65+'@example.invalid'),
    (('owner','broker','issuer'), 'http://example.invalid'),
    (('owner','broker','issuer'), 'https://user@example.invalid'),
    (('owner','broker','issuer'), 'https://example.invalid:bad'),
    (('owner','broker','issuer'), 'https://example.invalid/?query=1'),
    (('owner','broker','issuer'), 'https://example.invalid/#fragment'),
    (('owner','broker','issuer'), 'https://example.invalid\\path'),
    (('owner','broker','issuer'), None),
    (('owner','broker','audience'), ''), (('owner','broker','audience'), ['web']),
    (('binding','version'), True), (('binding','sea_public_key'), 'A'*43+'.'+'A'*43),
    (('binding','entra','audience'), 'common'), (('binding','entra','subject'), 'new\n'),
    (('binding','entra','broker'), '../microsoft'),
    (('binding','platform_admin','spanopticon'), 1),
    (('binding','keycloak_admin','enabled'), 'true'),
    (('binding','organizations','fyberlabs','roles'), []),
    (('binding','organizations','fyberlabs','roles'), ['owner','owner']),
    (('binding','organizations','fyberlabs','roles'), ['platform-admin']),
])
def test_invalid_mapping_fields_are_redacted(path, value):
    config = mapping()
    target = config
    for key in path[:-1]: target = target[key]
    target[path[-1]] = value
    with pytest.raises(InvalidBinding, match='^Startup identity configuration refused$'):
        validate(config)


def test_binding_changes_need_a_new_matching_fingerprint():
    config = mapping()
    config['binding']['organizations']['fyberlabs']['roles'] = ['owner']
    with pytest.raises(InvalidBinding): validate(config)
    config['binding_sha256'] = binding_fingerprint(config['binding'])
    assert validate(config)['binding']['organizations']['fyberlabs']['roles'] == ['owner']
    # Cross-tenant scope is explicit data. Each owner must reject unsupported scopes before writes.
    config['binding']['organizations']['fyberlabs']['tenant_id'] = config['binding']['entra']['tenant_id']
    config['binding_sha256'] = binding_fingerprint(config['binding'])
    assert validate(config) == config


def test_broker_claims_preserve_subject_and_ignore_profile_and_roles():
    config = mapping(); token = claims(config)
    assert verify_claims(config, token) == 'opaque-person'
    token.update(email='different@example.invalid', roles=['admin'])
    token['aud'] = ['another-client', config['owner']['broker']['audience']]
    assert verify_claims(config, token, expected_subject='opaque-person') == 'opaque-person'
    with pytest.raises(InvalidBinding): verify_claims(config, token, expected_subject='different-person')
    token.pop('azp')
    assert verify_claims(config, token) == 'opaque-person'


@pytest.mark.parametrize('field,value', [
    ('iss','https://different.invalid'), ('aud','different'), ('aud',[]), ('aud',[True]),
    ('aud',['s3rch-web','s3rch-web']), ('aud',None), ('aud',['s3rch-web']*33),
    ('azp','other'), ('login_provider','github'), ('entra_tenant_id','other'),
    ('entra_object_id','other'), ('entra_object_id',None), ('sub',''), ('sub','x\n'),
    ('sub','x'*256), ('sub',True), ('purpose',''), ('spanopticon_auth',False),
])
def test_wrong_account_or_token_kind_never_matches_email(field, value):
    config = mapping(); token = claims(config)
    token.update(email=config['owner']['profile']['email'], **{field:value})
    with pytest.raises(InvalidBinding): verify_claims(config, token)


def test_raw_entra_id_token_is_not_a_broker_token():
    config = mapping(); entra = config['binding']['entra']
    raw = {'ver':'2.0','tid':entra['tenant_id'],'oid':entra['object_id'],
           'iss':entra['issuer'],'aud':entra['audience'],'sub':entra['subject']}
    with pytest.raises(InvalidBinding): verify_claims(config, raw)
    with pytest.raises(InvalidBinding): verify_claims(config, None)


def test_private_load_rejects_unsafe_files_and_duplicate_json(tmp_path):
    path = tmp_path/'mapping.json'
    path.write_bytes(FIXTURE.read_bytes()); path.chmod(0o600)
    assert load(path) == mapping()
    path.chmod(0o640)
    with pytest.raises(InvalidBinding): load(path)
    path.chmod(0o600)
    alias = tmp_path/'alias'; alias.symlink_to(path)
    with pytest.raises(InvalidBinding): load(alias)
    alias.unlink(); os.link(path, alias)
    with pytest.raises(InvalidBinding): load(path)
    alias.unlink()
    with patch('os.geteuid', return_value=os.geteuid()+1):
        with pytest.raises(InvalidBinding): load(path)
    with pytest.raises(InvalidBinding): load(tmp_path)
    with pytest.raises(InvalidBinding): load(tmp_path/'absent')
    for raw in [b'', b'\xff', b'null', b'{}', b'{"schema_version":1,"schema_version":1}', b'x'*16385, b'['*3000]:
        path.write_bytes(raw)
        with pytest.raises(InvalidBinding): load(path)
    for value in [None, [], {'unexpected':float('nan')}, {'unexpected':'x'*17000}]:
        with pytest.raises(InvalidBinding): validate(value)


def test_canonical_binding_rejects_ambiguous_keys_and_scopes():
    original = mapping()['binding']
    for raw in [None, b'', b'x'*16385]:
        with pytest.raises(InvalidBinding): canonical_binding(raw)
    variants = []
    for field, value in [('tenant_id', None), ('issuer', 'https://login.microsoftonline.com/common/v2.0')]:
        doc = copy.deepcopy(original); doc['entra'][field] = value; variants.append(doc)
    for key in ['', original['sea_public_key'].replace('wpY.', 'wpZ.')]:
        doc = copy.deepcopy(original); doc['sea_public_key'] = key; variants.append(doc)
    doc = copy.deepcopy(original)
    doc['organizations']['fyberlabs']['organization_id'] = doc['organizations']['hyperme.sh']['organization_id']
    variants.append(doc)
    for doc in variants:
        with pytest.raises(InvalidBinding): canonical_binding(json.dumps(doc).encode())
