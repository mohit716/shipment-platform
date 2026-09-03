from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


class TokenError(Exception):
    """Raised when a token is missing, expired, tampered with or malformed.

    One exception type for every failure on purpose. Telling a caller whether a
    token expired or the signature was forged hands an attacker a free oracle,
    so the API layer turns all of these into the same 401.
    """


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Mint a signed access token identifying the given subject.

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
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def read_access_token(token: str) -> str:
    """Verify a token and return the subject it identifies.

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
    return subject
