from importlib.metadata import metadata, version

from fastapi import FastAPI
from safir.dependencies.arq import arq_dependency
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from .config import config
from .routers import (
    actions,
    adders,
    campaigns,
    groups,
    index,
    jobs,
    loaders,
    pipetask_error_types,
    productions,
    queries,
    script_templates,
    scripts,
    spec_blocks,
    steps,
    updates,
)

__all__ = ["app", "config"]


configure_logging(profile=config.profile, log_level=config.log_level, name=config.logger_name)
configure_uvicorn_logging(config.log_level)


tags_metadata = [
    {
        "name": "Loaders",
        "description": "Operations that load Objects in to the DB.",
    },
    {
        "name": "Query",
        "description": "Operations query exsiting Objects in to the DB.",
    },
    {
        "name": "Actions",
        "description": "Operations perform actions on existing Objects in to the DB."
        "In many cases this will result in the creating of new objects in the DB.",
    },
    {
        "name": "Adders",
        "description": "Operations explicitly add new Objects in to the DB."
        "These are typically used when we need to do something unexpected",
    },
    {
        "name": "Updates",
        "description": "Operations update Objects in to the DB."
        "These are typically used when we need to do something unexpected",
    },
    {
        "name": "Productions",
        "description": "Operations with `production`s. A `production` is a container for `campaign`s. "
        "`production`s must be uniquely named.",
    },
    {
        "name": "Campaigns",
        "description": "Operations with `campaign`s. A `campaign` consists of several processing `step`s "
        "which are run sequentially. A `campaign` also holds configuration such as a URL for a butler repo "
        "and a production area. `campaign`s must be uniquely named withing a given `production`.",
    },
    {
        "name": "Steps",
        "description": "Operations with `step`s. A `step` consists of several processing `group`s which "
        "may be run in parallel. `step`s must be uniquely named within a give `campaign`.",
    },
    {
        "name": "Groups",
        "description": "Operations with `groups`. A `group` can be processed in a single `workflow`, "
        "but we also need to account for possible failures. `group`s must be uniquely named within a "
        "given `step`.",
    },
    {
        "name": "Scripts",
        "description": "Operations with `scripts`. A `script` does a single operation, either something"
        "that is done asynchronously, such as making new collections in the Butler, or creating"
        "new objects in the DB, such as new `steps` and `groups`.",
    },
    {
        "name": "Jobs",
        "description": "Operations with `jobs`. A `job` runs a single `workflow`: keeps a count"
        "of the results data products and keeps track of associated errors.",
    },
    {"name": "PipetaskErrorTypes", "description": "Operations with `pipetask_error_types`."},
]


app = FastAPI(
    title="cm-service",
    description=metadata("lsst-cm-service")["Summary"],
    version=version("lsst-cm-service"),
    openapi_url=f"{config.prefix}/openapi.json",
    openapi_tags=tags_metadata,
    docs_url=f"{config.prefix}/docs",
    redoc_url=f"{config.prefix}/redoc",
)
"""The main FastAPI application for cm-service."""

app.add_middleware(XForwardedMiddleware)

app.include_router(index.router)
app.include_router(loaders.router, prefix=config.prefix)
app.include_router(queries.router, prefix=config.prefix)
app.include_router(actions.router, prefix=config.prefix)
app.include_router(adders.router, prefix=config.prefix)
app.include_router(updates.router, prefix=config.prefix)
app.include_router(productions.router, prefix=config.prefix)
app.include_router(campaigns.router, prefix=config.prefix)
app.include_router(steps.router, prefix=config.prefix)
app.include_router(groups.router, prefix=config.prefix)
app.include_router(scripts.router, prefix=config.prefix)
app.include_router(script_templates.router, prefix=config.prefix)
app.include_router(jobs.router, prefix=config.prefix)
app.include_router(pipetask_error_types.router, prefix=config.prefix)
app.include_router(spec_blocks.router, prefix=config.prefix)


@app.on_event("startup")
async def startup_event() -> None:
    await db_session_dependency.initialize(config.database_url, config.database_password)
    assert db_session_dependency._engine is not None  # pylint:  disable=protected-access
    db_session_dependency._engine.echo = config.database_echo  # pylint: disable=protected-access
    await arq_dependency.initialize(mode=config.arq_mode, redis_settings=config.arq_redis_settings)


@app.on_event("shutdown")
async def shutdown_event() -> None:  # pragma: no cover
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()
