from importlib.metadata import metadata, version

from fastapi import FastAPI
from safir.dependencies.arq import arq_dependency
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from .config import config
from .routers import (
    expert_campaigns,
    expert_groups,
    expert_jobs,
    expert_pipetask_error_types,
    expert_pipetask_errors,
    expert_product_sets,
    expert_productions,
    expert_row,
    expert_script_dependencies,
    expert_script_errors,
    expert_scripts,
    expert_spec_blocks,
    expert_specifications,
    expert_step_dependencies,
    expert_steps,
    expert_task_sets,
    index,
)

__all__ = ["app", "config"]


configure_logging(profile=config.profile, log_level=config.log_level, name=config.logger_name)
configure_uvicorn_logging(config.log_level)


tags_metadata = [
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
app.include_router(expert_specifications.router, prefix=config.prefix)
app.include_router(expert_spec_blocks.router, prefix=config.prefix)
app.include_router(expert_productions.router, prefix=config.prefix)
app.include_router(expert_campaigns.router, prefix=config.prefix)
app.include_router(expert_steps.router, prefix=config.prefix)
app.include_router(expert_groups.router, prefix=config.prefix)
app.include_router(expert_scripts.router, prefix=config.prefix)
app.include_router(expert_jobs.router, prefix=config.prefix)
app.include_router(expert_step_dependencies.router, prefix=config.prefix)
app.include_router(expert_script_dependencies.router, prefix=config.prefix)
app.include_router(expert_pipetask_error_types.router, prefix=config.prefix)
app.include_router(expert_pipetask_errors.router, prefix=config.prefix)
app.include_router(expert_script_errors.router, prefix=config.prefix)
app.include_router(expert_task_sets.router, prefix=config.prefix)
app.include_router(expert_product_sets.router, prefix=config.prefix)
app.include_router(expert_row.router, prefix=config.prefix)


@app.on_event("startup")
async def startup_event() -> None:
    await db_session_dependency.initialize(config.database_url, config.database_password)
    assert db_session_dependency._engine is not None  # pylint: disable=protected-access
    db_session_dependency._engine.echo = config.database_echo  # pylint: disable=protected-access
    await arq_dependency.initialize(mode=config.arq_mode, redis_settings=config.arq_redis_settings)


@app.on_event("shutdown")
async def shutdown_event() -> None:  # pragma: no cover
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()
