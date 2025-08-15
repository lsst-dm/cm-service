from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from . import __version__
from .common.flags import Features
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

configure_uvicorn_logging(config.logging.level)
configure_logging(profile=config.logging.profile, log_level=config.logging.level, name=config.asgi.title)


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
    uvicorn.run(
        "lsst.cmservice.main:app", host=config.asgi.host, port=config.asgi.port, reload=config.asgi.reload
    )
