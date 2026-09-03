import base64
import json

import jwt
import pytest

from app.core.config import settings
from app.core.tokens import TokenError, create_access_token, read_access_token


def test_a_token_round_trips_its_subject() -> None:
    assert read_access_token(create_access_token("42")) == "42"


def test_the_claims_are_readable_without_the_secret() -> None:
    # A JWT is signed, not encrypted. Anyone holding it can read the payload,
    # which is why a token must never carry anything secret.
    token = create_access_token("42")
    payload_segment = token.split(".")[1]
    padded = payload_segment + "=" * (-len(payload_segment) % 4)
    claims = json.loads(base64.urlsafe_b64decode(padded))
    assert claims["sub"] == "42"
    assert "exp" in claims and "iat" in claims


def test_a_token_signed_with_another_secret_is_rejected() -> None:
    forged = jwt.encode({"sub": "1"}, "some-other-secret", algorithm="HS256")
    with pytest.raises(TokenError):
        read_access_token(forged)


def test_an_edited_token_is_rejected() -> None:
    header, payload, signature = create_access_token("42").split(".")
    # Flip a character in the payload; the signature no longer matches.
    tampered = f"{header}.{payload[:-2] + ('AB' if payload[-2:] != 'AB' else 'CD')}.{signature}"
    with pytest.raises(TokenError):
        read_access_token(tampered)


def test_an_expired_token_is_rejected() -> None:
    with pytest.raises(TokenError):
        read_access_token(create_access_token("42", expires_minutes=-1))


def test_an_alg_none_token_is_rejected() -> None:
    # The classic JWT attack: a forged token asking to be verified with no
    # algorithm at all. Pinning algorithms on decode is what defeats it.
    unsigned = jwt.encode({"sub": "1"}, key="", algorithm="none")
    with pytest.raises(TokenError):
        read_access_token(unsigned)


def test_a_token_without_a_subject_is_rejected() -> None:
    empty = jwt.encode({"iat": 0}, settings.secret_key, algorithm="HS256")
    with pytest.raises(TokenError):
        read_access_token(empty)
