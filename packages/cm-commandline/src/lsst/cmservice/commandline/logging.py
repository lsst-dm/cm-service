"""Provide a common application root logger."""

import logging
import sys
from collections.abc import Callable
from typing import Annotated, Literal

import structlog
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingConfiguration(BaseSettings):
    """Configuration for the application's logging facility."""

    model_config = SettingsConfigDict(
        env_prefix="LOGGING__",
        case_sensitive=False,
        extra="ignore",
    )

    handle: str = Field(
        default="cm-service",
        title="Logger Name",
        description="Handle or name of the root logger",
    )

    level: Annotated[
        int, BeforeValidator(lambda v: getattr(logging, v.upper()) if isinstance(v, str) else v)
    ] = Field(
        default=logging.INFO, title="Log level", description="Logging level for the application's logs."
    )

    profile: Literal["development", "production"] = Field(
        default="development",
        title="Logging profile",
        description="Production generates structured JSON logs, Development generates console messages",
    )

    stream: Literal["stdout", "stderr"] = Field(
        default="stdout",
        title="Logging stream destination",
    )


def configure_logging(log_level: int) -> None:
    """Configures application for structured logging at the given log level."""

    shared_processors: list[Callable] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if log_level == logging.DEBUG:
        shared_processors.append(structlog.processors.CallsiteParameterAdder())

    log_renderer: structlog.types.Processor
    if LOGGER_SETTINGS.profile == "development":
        log_renderer = structlog.dev.ConsoleRenderer()
    else:
        log_renderer = structlog.processors.JSONRenderer()
        shared_processors.append(structlog.processors.format_exc_info)

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Core logging setup
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            log_renderer,
        ]
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Feed third-party logs to our root logger, except the Unvicorn access log,
    # for which we have a custom implementation as middleware.
    for logger, propagate in [
        ("httpx", True),
    ]:
        logging.getLogger(logger).handlers.clear()
        logging.getLogger(logger).propagate = propagate


# Module level actions
LOGGER_SETTINGS = LoggingConfiguration()
"""Settings object with runtime Logger configuration details."""

LOGGER_STREAM = sys.stdout if LOGGER_SETTINGS.stream == "stdout" else sys.stderr
logging.basicConfig(stream=LOGGER_STREAM)

configure_logging(LOGGER_SETTINGS.level)

# TODO: type annotated with the `wrapper_class` used in `structlog.configure()`
LOGGER = structlog.get_logger(LOGGER_SETTINGS.handle)
"""Module-level LOGGER object suitable for import in other modules to bind a
logger.
"""
