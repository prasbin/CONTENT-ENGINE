"""Authentication abstraction.

Phase 1 ships a static bearer-token provider plus a development-only
open provider. The protocol allows swapping in JWT/OAuth/etc. later
without touching route code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.core.errors import AuthenticationError

if TYPE_CHECKING:
    from app.core.config import Settings


class AuthProvider(Protocol):
    """Verifies caller credentials.

    Implementations must raise :class:`AuthenticationError` when the
    caller is not authenticated, and return normally otherwise.
    """

    def verify(self, credentials: str | None) -> None: ...


class TokenAuthProvider:
    """Constant-time comparison of a static bearer token from CE_API_TOKEN."""

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("token must not be empty")
        self._token = token

    def verify(self, credentials: str | None) -> None:
        import secrets

        if credentials is None:
            raise AuthenticationError("missing bearer token")
        if not secrets.compare_digest(credentials, self._token):
            raise AuthenticationError("invalid bearer token")


class AllowAllAuthProvider:
    """Development-only provider that accepts every caller.

    Used when CE_API_TOKEN is not configured. Never acceptable in production.
    """

    def verify(self, credentials: str | None) -> None:
        return None


def build_auth_provider(settings: Settings) -> AuthProvider:
    """Choose the auth provider based on configuration."""
    if settings.ce_api_token:
        return TokenAuthProvider(settings.ce_api_token)
    return AllowAllAuthProvider()


def extract_bearer(header_value: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer <token>`` header."""
    if header_value is None:
        return None
    scheme, _, token = header_value.partition(" ")
    if scheme.lower() != "bearer":
        raise AuthenticationError("expected 'Authorization: Bearer <token>'")
    token = token.strip()
    return token or None
