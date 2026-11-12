import json
from pathlib import Path
import unittest
from controlplane_identity.startup import validate, fingerprint, verify_claims


class StartupContractTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).parent / 'fixtures/startup-identity.json').read_text())
        self.claims = {'iss': self.config['issuer'], 'aud': self.config['audience'],
            'sub': 'opaque-broker-user', 'login_provider': 'microsoft',
            'entra_tenant_id': self.config['entra_tenant_id'], 'entra_object_id': self.config['entra_account_id']}

    def test_configured_tuple_selects_person_without_email(self):
        self.assertEqual(verify_claims(self.config, self.claims), 'opaque-broker-user')
        self.assertEqual(fingerprint(self.config), fingerprint(dict(reversed(list(self.config.items())))))

    def test_wrong_or_missing_binding_is_refused_without_values(self):
        for field in ('iss','aud','sub','entra_tenant_id','entra_object_id','login_provider'):
            for wrong in (None, 'sensitive-wrong-binding'):
                with self.subTest(field=field, wrong=wrong):
                    claims = dict(self.claims, **{field:wrong}, email=self.config['email'])
                    with self.assertRaises(ValueError) as raised: verify_claims(self.config, claims, expected_subject='opaque-broker-user')
                    self.assertNotIn('sensitive-wrong-binding', str(raised.exception))

    def test_session_and_privilege_claims_do_not_override_external_identity(self):
        claims = dict(self.claims, spanopticon_auth='tenant_session', realm_access={'roles':['admin']})
        with self.assertRaises(ValueError): verify_claims(self.config, claims)
        claims = dict(self.claims, entra_object_id='wrong', realm_access={'roles':['admin']})
        with self.assertRaises(ValueError): verify_claims(self.config, claims)

    def test_only_declared_organizations_and_existing_curve_key_are_valid(self):
        for field, value in [('organizations',['fyberlabs']*3), ('sea_public_key','A'*43+'.'+'A'*43),
                             ('entra_account_id',''), ('schema_version',True)]:
            with self.subTest(field=field), self.assertRaises(ValueError): validate(dict(self.config, **{field:value}))
