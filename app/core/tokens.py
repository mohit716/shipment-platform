from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt

from app.core.config import settings


class TokenError(Exception):
    """Raised when a token is missing, expired, tampered with or malformed.

    One exception type for every failure on purpose. Telling a caller whether a
    token expired or the signature was forged hands an attacker a free oracle,
    so the API layer turns all of these into the same 401.
    """


class TokenPurpose(str, Enum):
    """What a token is allowed to be used for.

    Every token carries one and every reader demands one. Without this a
    verification link, which is emailed in plaintext and often logged by mail
    servers, would work as an access token: same signature, same secret, same
    subject. That confusion is the whole reason the claim exists.
    """

    access = "access"
    verify_email = "verify_email"
    reset_password = "reset_password"


def create_token(
    subject: str,
    purpose: TokenPurpose,
    expires_minutes: int | None = None,
) -> str:
    """Mint a signed token identifying a subject for one specific purpose.

    A JWT is not encrypted, only signed: anyone holding it can read the claims.
    The signature proves this server issued it and that nothing has been edited
    since, which is all that is needed to trust the user id inside.
    """
    minutes = expires_minutes or settings.access_token_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        # Registered claim names, not invented ones, so any JWT library agrees
        # on their meaning: sub is the subject, iat issued-at, exp expiry.
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "purpose": purpose.value,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Mint a token for calling the API."""
    return create_token(subject, TokenPurpose.access, expires_minutes)


def read_token(token: str, expected: TokenPurpose) -> str:
    """Verify a token for one purpose and return the subject it identifies.

    The algorithm is pinned to a list rather than read from the token's own
    header. Trusting the header is the classic JWT attack: a forged token can
    ask to be verified with "none", or with HMAC against a public key.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    subject = payload.get("sub")
    if not subject:
        raise TokenError("Token carries no subject.")

    # A missing purpose is rejected rather than assumed. Tokens minted before
    # the claim existed must stop working, not silently pass as access tokens.
    if payload.get("purpose") != expected.value:
        raise TokenError("Token was not issued for this purpose.")
    return subject


def read_access_token(token: str) -> str:
    """Verify a token for calling the API and return its subject."""
    return read_token(token, TokenPurpose.access)
