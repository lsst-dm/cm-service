from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from safir.dependencies.http_client import http_client_dependency
from safir.middleware.x_forwarded import XForwardedMiddleware

from . import __version__
from .common.flags import Features
from .common.logging import LOGGER, LoggingMiddleware
from .config import config
from .db.session import db_session_dependency
from .routers import (
    healthz,
    index,
    tags_metadata,
    v1,
    v2,
)
from .web_app import web_app

logger = LOGGER.bind(module=__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Hook FastAPI init/cleanups."""
    app.state.tasks = set()
    # Dependency inits before app starts running
    await db_session_dependency.initialize()
    assert db_session_dependency.engine is not None

    # App runs here...
    yield

    # Dependency cleanups after app is finished
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()


app = FastAPI(
    lifespan=lifespan,
    title=config.asgi.title,
    version=__version__,
    openapi_url="/docs/openapi.json",
    openapi_tags=tags_metadata,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(LoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["X-Requested-With", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(XForwardedMiddleware)

app.include_router(healthz.health_router, prefix="")
app.include_router(index.router, prefix="")
if Features.API_V1 in config.features.enabled:
    app.include_router(v1.router, prefix=config.asgi.prefix)
if Features.API_V2 in config.features.enabled:
    app.include_router(v2.router, prefix=config.asgi.prefix)

# Start the frontend web application.
if Features.WEBAPP_V1 in config.features.enabled:
    app.mount(config.asgi.frontend_prefix, web_app)


if __name__ == "__main__":
    logger.info("Starting API Server...")
    uvicorn.run(
        "lsst.cmservice.main:app",
        host=config.asgi.host,
        port=config.asgi.port,
        reload=config.asgi.reload,
        log_config=None,
    )
