"""Immutable account matching after the caller verifies an Entra ID token.

This does not decode tokens, prove a SEA key, authorize reconciliation, or grant
roles. The owning service verifies signature, issuer, audience, time and nonce
before passing claims from its configured broker.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from uuid import UUID


class EntraBindingError(ValueError):
    def __init__(self) -> None:
        super().__init__('Entra account binding refused')


def _uuid(value: object) -> None:
    if type(value) is not str or len(value) != 36:
        raise EntraBindingError()
    try:
        parsed = UUID(value)
    except ValueError:
        raise EntraBindingError() from None
    if not parsed.int or str(parsed) != value:
        raise EntraBindingError()


@dataclass(frozen=True, slots=True, repr=False)
class EntraAccountBinding:
    tenant_id: str
    object_id: str
    issuer: str
    audience: str
    subject: str
    broker: str

    def __post_init__(self) -> None:
        for value in (self.tenant_id, self.object_id, self.audience):
            _uuid(value)
        if type(self.issuer) is not str or self.issuer != f'https://login.microsoftonline.com/{self.tenant_id}/v2.0':
            raise EntraBindingError()
        if type(self.subject) is not str or re.fullmatch(r'[\x21-\x7e]{1,256}', self.subject) is None:
            raise EntraBindingError()
        if type(self.broker) is not str or re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', self.broker) is None:
            raise EntraBindingError()

    @classmethod
    def from_config(cls, value: object) -> EntraAccountBinding:
        """Accept exactly the private Infra startup configuration's Entra object."""
        if type(value) is not dict or set(value) != {'tenant_id', 'object_id', 'issuer', 'audience', 'subject', 'broker'}:
            raise EntraBindingError()
        return cls(**value)

    def matches_verified_id_token(self, claims: object, *, broker: str) -> bool:
        """Compare verified v2 ID claims; never use email/name or token roles.

        The broker argument comes from server configuration, not a token claim
        or request field. A match is an account selector, not authentication.
        """
        if type(claims) is not dict or type(broker) is not str or broker != self.broker:
            return False
        expected = {'ver': '2.0', 'tid': self.tenant_id, 'oid': self.object_id,
                    'iss': self.issuer, 'aud': self.audience, 'sub': self.subject}
        return all(type(claims.get(key)) is str and claims[key] == value for key, value in expected.items())
