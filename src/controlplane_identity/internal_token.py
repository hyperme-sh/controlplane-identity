"""Compare internal settle tokens. Not a browser JWT door."""

from __future__ import annotations

import hmac
from collections.abc import Iterable

from fastapi import Request


INTERNAL_TOKEN_HEADER = "X-Internal-Token"


def provided_internal_token(request: Request) -> str | None:
    raw = request.headers.get(INTERNAL_TOKEN_HEADER)
    if raw is None or not str(raw).strip():
        return None
    return str(raw).strip()


def internal_token_matches_any(provided: str | None, expected: Iterable[str | None]) -> bool:
    """Compare every non-empty candidate without an early successful return."""
    matched = False
    for candidate in expected:
        if candidate:
            matched |= hmac.compare_digest((provided or "").encode("utf-8"), candidate.encode("utf-8"))
    return bool(provided) and matched


def internal_token_matches(provided: str | None, expected: str | None) -> bool:
    return internal_token_matches_any(provided, (expected,))


def request_has_internal_token(request: Request, expected: str | None | Iterable[str | None]) -> bool:
    candidates = (expected,) if isinstance(expected, str) or expected is None else expected
    return internal_token_matches_any(provided_internal_token(request), candidates)
