"""Explicit transition for signed legacy Auth credentials; never mint tokens.

The canonical identity distribution and its validators remain unchanged. Services
must deliberately import this package and enable the transition in configuration.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import jwt
from jwt import InvalidTokenError

from controlplane_identity.configuration import settings
from controlplane_identity.security.api_key_exchange_jwt import (
    try_decode_api_key_session_jwt as _canonical_api_key,
)
from controlplane_identity.security.tenant_session_jwt import (
    is_smoke_session,
    try_decode_host_setup_session as _canonical_host_setup,
    try_decode_tenant_session_jwt as _canonical_tenant,
)

_CANONICAL_TENANT = "https://spanopticon.dev/tenant_id"
_LEGACY_TENANT = "https://panopticon.dev/tenant_id"
_SETUP = "hypermesh-host-setup"


def _legacy(token: str, kind: str) -> dict[str, Any] | None:
    if os.environ.get("CONTROLPLANE_ACCEPT_LEGACY_AUTH") != "1":
        return None
    secret = settings.usable_api_key_exchange_secret()
    if not secret:
        return None
    issuer = f"https://panopticon.internal/{kind}"
    try:
        payload = jwt.decode(
            token, secret, algorithms=["HS256"], issuer=issuer,
            audience=_SETUP if kind == "host-setup" else None,
            options={"require": ["exp", "sub", "iss"]},
        )
        tenants = [uuid.UUID(str(payload[key])) for key in
                   ("tenant_id", _LEGACY_TENANT, _CANONICAL_TENANT) if key in payload]
    except (InvalidTokenError, ValueError, TypeError, AttributeError):
        return None
    if not payload.get("sub") or not tenants or len(set(tenants)) != 1:
        return None
    if kind == "host-setup":
        if (payload.get("aud") != _SETUP or payload.get("azp") != _SETUP
                or payload.get("purpose") != "host_setup"
                or "panopticon_auth" in payload or "spanopticon_auth" in payload
                or any(payload.get(key) for key in
                       ("realm_access", "resource_access", "roles", "permissions", "groups", "group"))):
            return None
    else:
        marker = "tenant_session" if kind == "tenant-session" else "api_key"
        if (payload.get("panopticon_auth") != marker
                or "spanopticon_auth" in payload
                or payload.get("azp") == _SETUP or payload.get("purpose") == "host_setup"):
            return None
        payload["spanopticon_auth"] = marker
    # Normalize only verified namespaced tenant context. Preserve original issuer,
    # subject, expiry, purpose, scopes, roles and classification for authorization.
    payload[_CANONICAL_TENANT] = str(tenants[0])
    return payload


def try_decode_tenant_session_jwt(token: str) -> dict[str, Any] | None:
    return _canonical_tenant(token) or _legacy(token, "tenant-session")


def try_decode_api_key_session_jwt(token: str) -> dict[str, Any] | None:
    return _canonical_api_key(token) or _legacy(token, "api-key")


def try_decode_host_setup_session(token: str) -> dict[str, Any] | None:
    return _canonical_host_setup(token) or _legacy(token, "host-setup")
