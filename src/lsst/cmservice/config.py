from urllib.parse import urlparse

from arq.connections import RedisSettings
from pydantic import BaseSettings, Field, RedisDsn
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile

__all__ = ["Configuration", "config"]


class Configuration(BaseSettings):
    """Configuration for cm-service."""

    prefix: str = Field(
        "/cm-service/v1",
        title="The URL prefix for the cm-service API",
        env="CM_URL_PREFIX",
    )

    database_url: str = Field(
        "",
        title="The URL for the cm-service database",
        env="CM_DATABASE_URL",
    )

    database_password: str | None = Field(
        title="The password for the cm-service database",
        env="CM_DATABASE_PASSWORD",
    )

    database_schema: str | None = Field(
        None,
        title="Schema to use for cm-service database",
        env="CM_DATABASE_SCHEMA",
    )

    database_echo: bool | str = Field(
        False,
        title="SQLAlchemy engine echo setting for the cm-service database",
        env="CM_DATABASE_ECHO",
    )

    profile: Profile = Field(
        Profile.development,
        title="Application logging profile",
        env="CM_LOG_PROFILE",
    )

    logger_name: str = Field(
        "cmservice",
        title="The root name of the application's logger",
        env="CM_LOGGER",
    )

    log_level: LogLevel = Field(
        LogLevel.INFO,
        title="Log level of the application's logger",
        env="CM_LOG_LEVEL",
    )

    arq_queue_url: RedisDsn = Field(
        RedisDsn("redis://localhost:6379/1", scheme="redis"),
        env="CM_ARQ_QUEUE_URL",
    )

    arq_mode: ArqMode = Field(
        ArqMode.production,
        env="CM_ARQ_MODE",
    )

    @property
    def arq_redis_settings(self) -> RedisSettings:
        """Create a Redis settings instance for arq."""
        url_parts = urlparse(self.arq_queue_url)
        redis_settings = RedisSettings(
            host=url_parts.hostname or "localhost",
            port=url_parts.port or 6379,
            database=int(url_parts.path.lstrip("/")) if url_parts.path else 0,
        )
        return redis_settings


config = Configuration()  # pyright: ignore
"""Configuration for cm-service."""
