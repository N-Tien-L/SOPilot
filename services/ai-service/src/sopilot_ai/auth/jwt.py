"""Access tokens issued by core-api (TECH-V2-core-api §5.1, TECH-V2-ai-service §4.1).

RS256, ``iss = sopilot-core``, ``aud`` contains ``sopilot-ai``; keys from core-api's JWKS (the
current and the previous key, so rotation does not drop sessions). ``wrole``/``wdept`` are taken
from the token, not re-read per request (ADR-007 §4.5, at most 15 minutes stale).
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

import jwt
import structlog
from fastapi import Header, HTTPException, Request, status

from sopilot_ai.retrieval.access_filter import Principal

log = structlog.get_logger(__name__)

ISSUER = "sopilot-core"
AUDIENCE = "sopilot-ai"
_LEEWAY_SECONDS = 60


class InvalidToken(Exception):
    pass


class TokenVerifier:
    """``key_for(token)`` returns the verification key; by default it is fetched from JWKS."""

    def __init__(self, jwks_url: str | None = None,
                 key_for: Callable[[str], Any] | None = None) -> None:
        if key_for is None:
            if not jwks_url:
                raise ValueError("a JWKS URL or a key resolver is required")
            client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)
            key_for = lambda token: client.get_signing_key_from_jwt(token).key  # noqa: E731
        self._key_for = key_for

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token, self._key_for(token), algorithms=["RS256"], audience=AUDIENCE,
                issuer=ISSUER, leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]})
            wdept = claims.get("wdept")
            return Principal(user_id=UUID(claims["sub"]), workspace_id=UUID(claims["wid"]),
                             role=claims["wrole"], department_id=UUID(wdept) if wdept else None)
        except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
            raise InvalidToken(type(exc).__name__) from exc

    async def verify_async(self, token: str) -> Principal:
        # PyJWKClient fetches over blocking HTTP on a cache miss.
        return await asyncio.to_thread(self.verify, token)


async def current_principal(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """FastAPI dependency: ``401`` with a generic message; the reason is only logged."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    verifier: TokenVerifier = request.app.state.token_verifier
    try:
        return await verifier.verify_async(token.strip())
    except InvalidToken as exc:
        log.info("access_token_rejected", reason=str(exc))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication required",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
