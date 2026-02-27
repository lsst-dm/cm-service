"""Provide a common application root logger."""

import logging
from collections.abc import Callable
from typing import Annotated, Literal

import structlog
from asgi_correlation_id import correlation_id
from fastapi import Request, Response
from pydantic import BeforeValidator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from structlog.typing import EventDict
from uvicorn.protocols.utils import get_path_with_query_string

SILENT_ROUTES = ["/healthz"]
"""Route names to silence (do not log access)"""

SILENT_MODULES: list[str] = []
"""Application modules to silence (do not log)"""


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


def silence_routes(logger: structlog.BoundLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """A structlog processor that prevents access logs for designated noisy
    routes or modules.
    """

    if any(
        [
            event_dict.get("http", {}).get("path") in SILENT_ROUTES,
            event_dict.get("module") in SILENT_MODULES,
        ]
    ):
        raise structlog.DropEvent
    return event_dict


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
        processors=shared_processors
        + [silence_routes, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
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
        ("uvicorn", True),
        ("uvicorn.error", True),
        ("uvicorn.access", False),
        ("httpx", True),
        ("httpcore", True),
        ("httpcore.http11", True),
        ("httpcore.connection", True),
        ("sqlalchemy.engine", True),
    ]:
        logging.getLogger(logger).handlers.clear()
        logging.getLogger(logger).propagate = propagate

    # set the BPS logging level
    for logger in [
        "lsst.ctrl.bps",
        "lsst.ctrl.bps.htcondor.htcondor_service",
    ]:
        logging.getLogger(logger).setLevel(logging.ERROR)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure correct logging from FastAPI application."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        structlog.contextvars.clear_contextvars()

        # Add the correlation request_id if one is available
        if request_id := correlation_id.get():
            structlog.contextvars.bind_contextvars(request_id=request_id)

        response = Response(status_code=500)
        try:
            response = await call_next(request)
        except Exception as e:
            structlog.stdlib.get_logger("api.error").exception(f"Uncaught exception: {e}")
            raise
        finally:
            # Construct and issue the access log for the request
            status_code = response.status_code
            url = get_path_with_query_string(request.scope)  # type: ignore[arg-type]
            if request.client is not None:
                client_host: str | None = request.client.host
                client_port: int | None = request.client.port
            else:
                client_host = client_port = None
            http_method = request.method
            http_version = request.scope["http_version"]
            structlog.stdlib.get_logger("api.access").info(
                f"""{client_host}:{client_port} - "{http_method} {url} HTTP/{http_version}" {status_code}""",
                http={
                    "url": str(request.url),
                    "path": request.scope.get("path"),
                    "query_string": request.scope.get("query_string", b"").decode("ascii"),
                    "status_code": status_code,
                    "method": http_method,
                    "request_id": request_id,
                    "version": http_version,
                },
                network={
                    "client": {"ip": client_host, "port": client_port},
                },
            )

            return response


# Module level actions
LOGGER_SETTINGS = LoggingConfiguration()
"""Settings object with runtime Logger configuration details."""

configure_logging(LOGGER_SETTINGS.level)

LOGGER = structlog.get_logger(LOGGER_SETTINGS.handle)
"""Module-level LOGGER object suitable for import in other modules to bind a
logger.
"""
