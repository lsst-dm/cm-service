from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, NoResultFound
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from . import __version__
from .common.flags import Features
from .common.logging import LOGGER, LoggingMiddleware
from .config import config
from .db.session import db_session_dependency
from .routers import healthz, tags_metadata

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


app = FastAPI(
    lifespan=lifespan,
    title=config.asgi.title,
    version=__version__,
    openapi_url=f"{config.asgi.docs_prefix}/openapi.json",
    openapi_tags=tags_metadata,
    docs_url=config.asgi.docs_prefix,
    redoc_url=None,
)

# Add Middlewares
app.add_middleware(LoggingMiddleware)
app.add_middleware(CorrelationIdMiddleware, generator=lambda: str(uuid4()))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["X-Requested-With", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"])

# Add Routers
app.include_router(healthz.health_router, prefix="")


# Add Exception Handlers
@app.exception_handler(NoResultFound)
async def notfound_error_handler(request: Request, exc: NoResultFound):
    """Raise a 404 when the `NoResultFound` exception is raised.

    The NoResultFound exception may be raised in a route that uses the
    `session.get_one()` method where it is an error for there not to be one.
    """
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@app.exception_handler(IntegrityError)
async def duplicate_error_handler(request: Request, exc: IntegrityError):
    """Raise a 409 when the `IntegrityError` exception is raised."""
    raise HTTPException(status_code=status.HTTP_409_CONFLICT)


# Add Features
if Features.API_V1 in config.features.enabled:
    from .routers import v1

    app.include_router(v1.router, prefix=config.asgi.route_prefix)
if Features.API_V2 in config.features.enabled:
    from .routers import v2

    app.include_router(v2.router, prefix=config.asgi.route_prefix)

# Start the frontend web application.
if Features.WEBAPP_V1 in config.features.enabled:
    from .web_app import web_app

    app.mount(config.asgi.frontend_prefix, web_app)


if __name__ == "__main__":
    logger.info("Starting API Server...")
    uvicorn.run(
        "lsst.cmservice.main:app",
        host=config.asgi.host,
        port=config.asgi.port,
        reload=config.asgi.reload,
        log_config=None,
        root_path=config.asgi.root_path,
        proxy_headers=True,
    )
