"""Inject application configuration without depending on the legacy API package."""

from typing import Protocol

# Fixed compatibility marker for sessions issued before smoke capability extraction.
LEGACY_SMOKE_SESSION_CLAIM = "hypermesh_smoke"


class IdentitySettings(Protocol):
    smoke_session_claim: str
    keycloak_jwks_url: str | None
    keycloak_issuer: str | None
    keycloak_client_id: str
    keycloak_jwks_request_host: str | None

    def usable_api_keys_internal_token(self) -> str | None: ...
    def usable_api_key_exchange_secret(self) -> str | None: ...
    def usable_api_key_exchange_secrets(self) -> tuple[str, ...]: ...
    def usable_api_keys_internal_tokens(self) -> tuple[str, ...]: ...
    def keycloak_allowed_audience_set(self) -> set[str]: ...
    def keycloak_allowed_azp_set(self) -> set[str]: ...


_configured: IdentitySettings | None = None


def configure_identity(configuration: IdentitySettings) -> None:
    global _configured
    _configured = configuration


class _SettingsProxy:
    def __getattr__(self, name: str):
        if _configured is None:
            raise RuntimeError(
                "Identity settings are not configured; call configure_identity first"
            )
        return getattr(_configured, name)


settings = _SettingsProxy()


def _rotation_values(plural: str, singular: str) -> tuple[str | None, ...]:
    method = getattr(settings, plural, None)
    if method is None:
        return (getattr(settings, singular)(),)
    values = method()
    if not isinstance(values, (tuple, list)) or any(
        value is not None and not isinstance(value, str) for value in values
    ):
        raise TypeError("Identity rotation settings must return a sequence of secrets")
    # Keep an empty current slot: callers must never mint with a previous key.
    return tuple(values)


def api_key_exchange_secrets() -> tuple[str | None, ...]:
    return _rotation_values("usable_api_key_exchange_secrets", "usable_api_key_exchange_secret")


def api_keys_internal_tokens() -> tuple[str | None, ...]:
    return _rotation_values("usable_api_keys_internal_tokens", "usable_api_keys_internal_token")
