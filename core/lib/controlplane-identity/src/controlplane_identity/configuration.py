"""Inject application configuration without depending on the legacy API package."""

from typing import Protocol


class IdentitySettings(Protocol):
    keycloak_jwks_url: str | None
    keycloak_issuer: str | None
    keycloak_client_id: str
    keycloak_jwks_request_host: str | None

    def usable_api_keys_internal_token(self) -> str | None: ...
    def usable_api_key_exchange_secret(self) -> str | None: ...
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
