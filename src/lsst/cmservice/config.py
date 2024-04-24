import os
from arq.connections import RedisSettings
from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings
from safir.arq import ArqMode
from safir.logging import LogLevel, Profile

__all__ = ["Configuration", "config"]


if not os.environ.get("CM_DATABASE_PASSWORD"):
    os.environ["CM_DATABASE_PASSWORD"] = "dummy"

if not os.environ.get("CM_ARQ_REDIS_PASSWORD"):
    os.environ["CM_ARQ_REDIS_PASSWORD"] = "dummy"


class Configuration(BaseSettings):
    """Configuration for cm-service."""

    prefix: str = Field(
        default="/cm-service/v1",
        title="The URL prefix for the cm-service API",
        validation_alias="CM_URL_PREFIX",
    )

    database_url: str = Field(
        default="",
        title="The URL for the cm-service database",
        validation_alias="CM_DATABASE_URL",
    )

    database_password: str | None = Field(
        title="The password for the cm-service database",
        validation_alias="CM_DATABASE_PASSWORD",
    )

    database_schema: str | None = Field(
        default=None,
        title="Schema to use for cm-service database",
        validation_alias="CM_DATABASE_SCHEMA",
    )

    database_echo: bool = Field(
        default=False,
        title="SQLAlchemy engine echo setting for the cm-service database",
        validation_alias="CM_DATABASE_ECHO",
    )

    profile: Profile = Field(
        default=Profile.development,
        title="Application logging profile",
        validation_alias="CM_LOG_PROFILE",
    )

    logger_name: str = Field(
        default="cmservice",
        title="The root name of the application's logger",
        validation_alias="CM_LOGGER",
    )

    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        title="Log level of the application's logger",
        validation_alias="CM_LOG_LEVEL",
    )

    arq_mode: ArqMode = Field(
        ArqMode.production,
    )

    arq_redis_url: RedisDsn = Field(
        default=RedisDsn("redis://localhost:6379/1"),
        title="The URL for the cm-service arq redis database",
        validation_alias="CM_ARQ_REDIS_URL",
    )

    arq_redis_password: str | None = Field(
        title="The password for the cm-service arq redis database",
        validation_alias="CM_ARQ_REDIS_PASSWORD",
    )

    @property
    def arq_redis_settings(self: "Configuration") -> RedisSettings:
        """Create a Redis settings instance for arq."""
        return RedisSettings(
            host=self.arq_redis_url.host or "localhost",
            port=int(self.arq_redis_url.port or 6379),
            password=self.arq_redis_password,
            database=int(self.arq_redis_url.path.lstrip("/")) if self.arq_redis_url.path else 0,
        )


config = Configuration()
"""Configuration for cm-service."""
