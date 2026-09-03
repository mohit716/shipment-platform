import pytest
from pydantic import ValidationError

from app.core.config import COMPOSE_SECRET, DEV_SECRET, Settings


def _production(**overrides: object) -> Settings:
    values = {
        "environment": "production",
        "debug": False,
        "database_echo": False,
        "secret_key": "a-unique-production-secret-key-32+",
        **overrides,
    }
    return Settings(**values)


def test_production_accepts_a_real_secret() -> None:
    settings = _production()
    assert settings.environment == "production"


def test_production_refuses_the_development_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _production(secret_key=DEV_SECRET)


def test_production_refuses_the_compose_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _production(secret_key=COMPOSE_SECRET)


def test_production_refuses_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        _production(debug=True)


def test_development_still_allows_the_dev_secret() -> None:
    # A laptop should not require a generated secret just to run uvicorn.
    settings = Settings(environment="development", secret_key=DEV_SECRET, debug=True)
    assert settings.debug is True
