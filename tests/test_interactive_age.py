"""Panopticon edge regressions now run at their shared identity owner."""
from types import SimpleNamespace
import pytest
from jwt import InvalidTokenError
from controlplane_identity import configuration
from controlplane_identity.configuration import settings
from controlplane_identity.security import keycloak_jwt as kc

@pytest.fixture(autouse=True)
def configured_settings(monkeypatch):
    monkeypatch.setattr(configuration, '_configured', SimpleNamespace(
        keycloak_allowed_audience_set=lambda: frozenset({'account'}),
        keycloak_allowed_azp_set=lambda: frozenset({'hypermesh-native'})))


def _interactive_validator(monkeypatch, payload):
    import controlplane_identity.security.keycloak_jwt as impl

    class _Key:
        key = "unused"

    class _Jwks:
        headers = None

        def get_signing_key_from_jwt(self, token: str):
            return _Key()

    validator = kc.KeycloakJWTValidator("http://jwks.example/certs", "http://kc.example/realms/controlplane", "")
    validator._jwks_client = _Jwks()
    monkeypatch.setattr(impl.jwt, "decode", lambda *args, **kwargs: payload)
    monkeypatch.setattr(settings, "keycloak_allowed_audience_set", lambda: frozenset({"account"}))
    monkeypatch.setattr(
        settings,
        "keycloak_allowed_azp_set",
        lambda: frozenset({
            "controlplane-frontend",
            "controlplane-mobile",
            "controlplane-device",
            "controlplane-m2m",
            "controlplane-api-key",
            "hypermesh-native",
        }),
    )
    return validator


@pytest.mark.parametrize("azp", ["controlplane-mobile", "hypermesh-native", "controlplane-frontend", "controlplane-device"])
def test_interactive_token_without_age_confirmation_is_rejected(monkeypatch, azp):
    validator = _interactive_validator(monkeypatch, {"azp": azp, "sub": "person", "account_type": "human"})
    with pytest.raises(InvalidTokenError, match="age confirmation required"):
        validator.validate_sync("header.payload.sig")


@pytest.mark.parametrize("azp", ["controlplane-mobile", "hypermesh-native"])
def test_interactive_token_with_age_timestamp_is_accepted(monkeypatch, azp):
    validator = _interactive_validator(
        monkeypatch,
        {"azp": azp, "sub": "person", "account_type": "human", "terms_and_conditions": 1761900000},
    )
    assert validator.validate_sync("header.payload.sig")["azp"] == azp


def test_machine_and_service_tokens_do_not_need_an_age_timestamp(monkeypatch):
    machine = _interactive_validator(monkeypatch, {"azp": "controlplane-m2m", "sub": "service-account"})
    assert machine.validate_sync("header.payload.sig")["azp"] == "controlplane-m2m"
    automation = _interactive_validator(
        monkeypatch,
        {"azp": "hypermesh-native", "sub": "renter", "account_type": "service"},
    )
    assert automation.validate_sync("header.payload.sig")["account_type"] == "service"
