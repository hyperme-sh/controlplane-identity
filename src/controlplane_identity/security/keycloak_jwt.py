"""Validate Keycloak access tokens (RS256 + JWKS)."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

import jwt
from jwt import InvalidTokenError, PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from controlplane_identity.account_lifecycle import require_open_account
from controlplane_identity.configuration import settings

logger = logging.getLogger(__name__)


_INTERACTIVE_AGE_CLIENTS = frozenset({
    "controlplane-frontend",
    "controlplane-mobile",
    "controlplane-device",
    "hypermesh-native",
})


def _age_confirmation_satisfied(payload: dict[str, object]) -> bool:
    """Service automation is exempt. Everyone else needs a positive Unix timestamp.

    Keycloak 26.5 can skip the required action when ``kc_action`` names it.
    The access token is the check that still holds for every interactive client.
    """
    if payload.get("account_type") == "service":
        return True
    raw = payload.get("terms_and_conditions")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if isinstance(raw, bool) or isinstance(raw, float):
        return False
    if isinstance(raw, int):
        return raw > 0
    if isinstance(raw, str) and raw.isdigit():
        return int(raw) > 0
    return False


class KeycloakJWTValidator:
    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        client_id: str,
        jwks_request_host: str | None = None,
    ) -> None:
        self._jwks_url = jwks_url
        self._issuer = issuer
        self._client_id = client_id  # legacy single-id; validation uses settings.keycloak_allowed_azp_set()
        jwks_headers: dict[str, str] = {}
        if jwks_request_host:
            jwks_headers["Host"] = jwks_request_host.strip()
        self._jwks_client = PyJWKClient(jwks_url, headers=jwks_headers or None)

    def validate_sync(self, token: str) -> dict[str, object]:
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        except PyJWKClientConnectionError as e:
            logger.warning(
                "JWKS fetch failed for %s (Host header: %s): %s",
                self._jwks_url,
                self._jwks_client.headers.get("Host") if self._jwks_client.headers else None,
                e,
            )
            raise
        allowed_aud = settings.keycloak_allowed_audience_set()
        if not allowed_aud:
            raise InvalidTokenError("no allowed Keycloak audiences configured")
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self._issuer,
            audience=list(allowed_aud),
            options={"verify_aud": True},
        )
        azp = payload.get("azp")
        allowed = settings.keycloak_allowed_azp_set()
        if azp == "hypermesh-host-setup" or azp not in allowed:
            raise InvalidTokenError(
                f"Invalid azp: {azp!r} not in allowed clients {sorted(allowed)!r}"
            )
        require_open_account(payload)
        return payload

    def validate_closure_operator_sync(
        self, token: str, *, client_ids: frozenset[str]
    ) -> dict[str, object]:
        """Native global closure grant, isolated from generic application trust.

        The caller supplies its immutable server-configured operator clients.
        Dedicated audiences never add those clients to ordinary API trust.
        """
        if (
            not isinstance(client_ids, frozenset) or not client_ids or len(client_ids) > 1000
            or any(not isinstance(value, str) or not value.strip() or len(value) > 512 for value in client_ids)
        ):
            raise InvalidTokenError("Explicit closure operator clients required")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token, signing_key.key, algorithms=["RS256"], issuer=self._issuer,
            audience="spanopticon-account-closure",
            options={"require": ["exp", "iat", "sub", "iss", "aud", "azp"]},
        )
        azp, subject = payload.get("azp"), payload.get("sub")
        roles = payload.get("realm_access")
        roles = roles.get("roles") if isinstance(roles, dict) else None
        if (
            not isinstance(azp, str) or azp not in client_ids
            or azp in {"hypermesh-host-setup", "account-closure-reader", "account-closure-worker"}
            or not isinstance(subject, str) or not subject.strip() or len(subject) > 512
            or subject.startswith("apikey:") or payload.get("spanopticon_auth")
            or payload.get("purpose") or "api_key_id" in payload or "key_id" in payload
            or not isinstance(roles, list) or not all(isinstance(role, str) for role in roles)
            or "account:close" not in roles
        ):
            raise InvalidTokenError("Native closure operator grant required")
        if azp in _INTERACTIVE_AGE_CLIENTS and not _age_confirmation_satisfied(payload):
            raise InvalidTokenError("age confirmation required")
        require_open_account(payload)
        return payload

    async def validate_closure_operator(
        self, token: str, *, client_ids: frozenset[str]
    ) -> dict[str, object]:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.validate_closure_operator_sync(token, client_ids=client_ids)
        )

    def validate_host_setup_sync(self, token: str) -> dict[str, object]:
        """Validate the device client only for the dedicated setup exchange."""
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token, signing_key.key, algorithms=["RS256"], issuer=self._issuer,
            audience="hypermesh-host-setup",
            options={"require": ["exp", "sub", "iss", "aud", "azp"]},
        )
        if payload.get("azp") != "hypermesh-host-setup" or not payload.get("sub"):
            raise InvalidTokenError("host setup client required")
        require_open_account(payload)
        return payload

    async def validate_host_setup(self, token: str) -> dict[str, object]:
        return await asyncio.get_running_loop().run_in_executor(
            None, self.validate_host_setup_sync, token,
        )

    async def validate(self, token: str) -> dict[str, object]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.validate_sync, token)


@lru_cache
def _validator_singleton() -> KeycloakJWTValidator:
    return KeycloakJWTValidator(
        jwks_url=settings.keycloak_jwks_url or "",
        issuer=settings.keycloak_issuer or "",
        client_id=settings.keycloak_client_id,
        jwks_request_host=settings.keycloak_jwks_request_host,
    )


def get_keycloak_jwt_validator() -> KeycloakJWTValidator:
    return _validator_singleton()
