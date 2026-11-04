"""Purpose-bound account lifecycle RPCs and fail-closed token retirement.

Core authorization checks current server state. The paid gateway explicitly uses
local durable revocations instead, preserving its offline ticket boundary.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import hmac
import os
import uuid
from urllib.parse import urlparse

import httpx
from jwt import InvalidTokenError

_offline = contextvars.ContextVar("account_lifecycle_offline", default=False)


def enforcement_enabled() -> bool:
    return os.environ.get("ACCOUNT_CLOSURE_ENFORCEMENT_ENABLED", "").lower() == "true"


def service_url(name: str) -> str:
    url = os.environ.get(name, "").rstrip("/")
    parsed = urlparse(url)
    local = os.environ.get("FASTAPI_ENV", "").lower() in {"development", "test"}
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
    ):
        raise RuntimeError("Account lifecycle service URL unavailable")
    return url


def service_secret(name: str) -> str:
    value = os.environ.get(name, "")
    other = (
        "ACCOUNT_CLOSURE_OPERATIONS_TOKEN"
        if name == "ACCOUNT_CLOSURE_GUARD_TOKEN"
        else "ACCOUNT_CLOSURE_GUARD_TOKEN"
    )
    same_purpose_secret = name in {
        "ACCOUNT_CLOSURE_GUARD_TOKEN",
        "ACCOUNT_CLOSURE_OPERATIONS_TOKEN",
    } and value == os.environ.get(other)
    if (
        len(value) < 32
        or not value.isascii()
        or any(ord(char) < 33 or ord(char) == 127 for char in value)
        or same_purpose_secret
    ):
        raise RuntimeError("Account lifecycle service credential unavailable")
    return value


def authorized_call(headers, *, mutation: bool = False) -> bool:
    if not enforcement_enabled():
        return False
    name = (
        "ACCOUNT_CLOSURE_OPERATIONS_TOKEN"
        if mutation
        else "ACCOUNT_CLOSURE_GUARD_TOKEN"
    )
    try:
        expected = service_secret(name)
    except RuntimeError:
        return False
    supplied = headers.get("X-Account-Lifecycle-Token", "")
    return (
        isinstance(supplied, str)
        and supplied.isascii()
        and hmac.compare_digest(expected, supplied)
    )


def subject_digest(tenant: uuid.UUID, subject: str) -> str:
    return hashlib.sha256(
        f"account-closure-v1\n{tenant}\n{subject}".encode()
    ).hexdigest()


def key_digest(tenant: uuid.UUID, identifier: uuid.UUID) -> str:
    return hashlib.sha256(
        f"account-key-closure-v1\n{tenant}\n{identifier}".encode()
    ).hexdigest()


@contextlib.contextmanager
def offline_gateway_verification():
    """Only the gateway: a durable local deny ledger must gate the verified grant."""
    token = _offline.set(True)
    try:
        yield
    finally:
        _offline.reset(token)


def require_open_account(claims: dict) -> None:
    if not enforcement_enabled() or _offline.get():
        return
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 512:
        raise InvalidTokenError("Account authorization unavailable")
    try:
        base = service_url("ACCOUNT_CLOSURE_GUARD_URL")
        credential = service_secret("ACCOUNT_CLOSURE_GUARD_TOKEN")
        with httpx.Client(timeout=3, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                base + "/api/v1/internal/account-lifecycle/check",
                headers={"X-Account-Lifecycle-Token": credential},
                json={
                    "subject": subject,
                    "tenant_id": claims.get(
                        "https://spanopticon.dev/tenant_id", claims.get("tenant_id")
                    ),
                },
            )
        result = response.json() if response.status_code == 200 else None
        if not isinstance(result, dict) or result.get("blocked") is not False:
            raise InvalidTokenError("Account is unavailable")
    except InvalidTokenError:
        raise
    except Exception:
        raise InvalidTokenError("Account authorization unavailable") from None


async def require_closure_permit(
    *, subject: str, closed_at, tenant_id: uuid.UUID | None
) -> None:
    """Mutation receivers verify the original closure time and registered scope."""
    if not enforcement_enabled() or closed_at.tzinfo is None:
        raise RuntimeError("Account closure permit unavailable")
    try:
        async with httpx.AsyncClient(
            timeout=3, trust_env=False, follow_redirects=False
        ) as client:
            response = await client.post(
                service_url("ACCOUNT_CLOSURE_GUARD_URL")
                + "/api/v1/internal/account-lifecycle/permit",
                headers={
                    "X-Account-Lifecycle-Token": service_secret(
                        "ACCOUNT_CLOSURE_GUARD_TOKEN"
                    ),
                    **({"X-Tenant-ID": str(tenant_id)} if tenant_id else {}),
                },
                json={
                    "subject": subject,
                    "closed_at": closed_at.isoformat(),
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
            )
        result = response.json() if response.status_code == 200 else None
        if not isinstance(result, dict) or result.get("allowed") is not True:
            raise RuntimeError("Account closure permit unavailable")
    except Exception:
        raise RuntimeError("Account closure permit unavailable") from None


async def closure_scope(*, subject: str, closed_at, tenant_id: uuid.UUID) -> dict:
    """Fetch canonical owner inventory and erasure authority from its recorder."""
    if not enforcement_enabled() or closed_at.tzinfo is None:
        raise RuntimeError("Account closure scope unavailable")
    try:
        async with httpx.AsyncClient(
            timeout=3, trust_env=False, follow_redirects=False
        ) as client:
            response = await client.post(
                service_url("ACCOUNT_CLOSURE_GUARD_URL")
                + "/api/v1/internal/account-lifecycle/scope",
                headers={
                    "X-Account-Lifecycle-Token": service_secret(
                        "ACCOUNT_CLOSURE_GUARD_TOKEN"
                    ),
                    "X-Tenant-ID": str(tenant_id),
                },
                json={
                    "subject": subject,
                    "closed_at": closed_at.isoformat(),
                    "tenant_id": str(tenant_id),
                },
            )
        result = response.json() if response.status_code == 200 else None
        if not isinstance(result, dict) or result.get("allowed") is not True:
            raise ValueError()
        if (
            not isinstance(result.get("user_ids"), list)
            or len(result["user_ids"]) > 100_000
        ):
            raise ValueError()
        if not isinstance(result.get("keys"), list) or len(result["keys"]) > 100_000:
            raise ValueError()
        if (
            type(result.get("keys_complete")) is not bool
            or type(result.get("erasure_allowed")) is not bool
        ):
            raise ValueError()
        if len({uuid.UUID(value) for value in result["user_ids"]}) != len(
            result["user_ids"]
        ):
            raise ValueError()
        renters = result.get("renter_ids")
        if (
            not isinstance(renters, list)
            or len(renters) > 100_000
            or type(result.get("renter_alias_ambiguous")) is not bool
        ):
            raise ValueError()
        if len({uuid.UUID(value) for value in renters}) != len(renters):
            raise ValueError()
        if not set(result["user_ids"]).issubset(renters):
            raise ValueError()
        key_ids = set()
        for key in result["keys"]:
            identifier = uuid.UUID(key["id"])
            if identifier in key_ids:
                raise ValueError()
            key_ids.add(identifier)
            fingerprint = key.get("fingerprint")
            if fingerprint is not None and (
                not isinstance(fingerprint, str)
                or len(fingerprint) != 64
                or any(char not in "0123456789abcdef" for char in fingerprint)
            ):
                raise ValueError()
        return result
    except Exception:
        raise RuntimeError("Account closure scope unavailable") from None
