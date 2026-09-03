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


@lru_cache
def get_settings() -> Settings:
    """Build the settings once and reuse them.

    Without the cache, every call re-reads .env from disk. The cache also makes
    the object easy to replace in tests through get_settings.cache_clear().
    """
    return Settings()


settings = get_settings()
