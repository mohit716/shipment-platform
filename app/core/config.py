from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from the environment, validated like any other model.

    Precedence runs real environment variables first, then .env, then the
    defaults below. That order is what lets a deployment platform inject
    DATABASE_URL without the .env file existing at all.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Fail loudly if .env carries a key nothing reads, which is usually a
        # typo in a variable name.
        extra="forbid",
    )

    app_name: str = "FleetLine"
    environment: str = "development"
    debug: bool = True

    database_url: str = (
        "postgresql+asyncpg://fleetline:fleetline@localhost:5433/fleetline"
    )

    # Echoing every SQL statement is useful while learning and far too noisy in
    # production, so it follows the environment rather than being hard coded.
    database_echo: bool = True

    # Signing key for access tokens. The default is a development placeholder;
    # phase 16 makes production refuse to start without a real one, because a
    # known secret means anyone can mint a token for any account.
    # At least 32 bytes: HS256 keys shorter than the hash output weaken the
    # signature, and PyJWT warns about it.
    secret_key: str = "dev-only-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"

    # Short lived on purpose. A token cannot be revoked once issued, so the
    # expiry is the only thing limiting the damage from a stolen one.
    access_token_expire_minutes: int = 30

    # bcrypt's work factor. Each step doubles the time to hash, which is the
    # point in production and pure waste in a test suite that hashes hundreds
    # of throwaway passwords, so the tests turn it down to the minimum.
    bcrypt_rounds: int = 12

    # console logs messages instead of sending them, which is what development
    # wants: a shipping demo that emails strangers is a bad afternoon.
    email_backend: str = "console"
    email_from: str = "no-reply@fleetline.example"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""

    # Where emailed links point. The API does not serve the verification page;
    # the dashboard does, and it posts the token back here.
    frontend_url: str = "http://localhost:5173"

    # Deliberately short. A verification link sits in an inbox indefinitely, so
    # the window in which a leaked one is useful should be small.
    verification_token_expire_minutes: int = 60

    # Shorter still. A reset link is a live credential for the account, so it
    # should be usable for about as long as it takes to read the email.
    reset_token_expire_minutes: int = 15

    # Adds an SMS channel alongside email. Off by default: every gateway needs
    # a paid account and a verified sender before it will deliver anything.
    sms_enabled: bool = False

    # Matches the redis service in docker-compose.yml. Database 0 carries the
    # queue and 1 the results, so flushing one does not destroy the other.
    celery_broker_url: str = "redis://localhost:6380/0"
    celery_result_backend: str = "redis://localhost:6380/1"


@lru_cache
def get_settings() -> Settings:
    """Build the settings once and reuse them.

    Without the cache, every call re-reads .env from disk. The cache also makes
    the object easy to replace in tests through get_settings.cache_clear().
    """
    return Settings()


settings = get_settings()
