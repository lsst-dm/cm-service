import os

from pydantic import Field
from pydantic_settings import BaseSettings
from safir.logging import LogLevel, Profile

__all__ = ["Configuration", "config"]


if not os.environ.get("CM_DATABASE_PASSWORD"):
    os.environ["CM_DATABASE_PASSWORD"] = "dummy"


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


config = Configuration()
"""Configuration for cm-service."""
