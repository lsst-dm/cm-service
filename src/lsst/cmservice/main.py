from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
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
    pipetask_errors,
    product_sets,
    productions,
    queries,
    queues,
    row,
    script_dependencies,
    script_errors,
    script_template_associations,
    script_templates,
    scripts,
    spec_block_associations,
    spec_blocks,
    specifications,
    step_dependencies,
    steps,
    task_sets,
    wms_task_reports,
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
    {
        "name": "Pipetask Error Types",
        "description": "Operations with `pipetask_error_type` table.",
    },
    {
        "name": "Pipetask Errors",
        "description": "Operations with `pipetask_error` table.",
    },
    {
        "name": "Product Sets",
        "description": "Operations with `product_set` table.",
    },
    {
        "name": "Task Sets",
        "description": "Operations with `task_set` table.",
    },
    {
        "name": "Script Dependencies",
        "description": "Operations with `script_dependency` table.",
    },
    {
        "name": "Step Dependencies",
        "description": "Operations with `step_dependency` table.",
    },
    {
        "name": "Wms Task Reports",
        "description": "Operations with `wms_task_report` table.",
    },
    {
        "name": "Rows",
        "description": "Generic row-based operations",
    },
    {"name": "Specifications", "description": "Operations with `specification` table."},
    {"name": "SpecBlocks", "description": "Operations with `spec_block` table."},
    {"name": "ScriptTemplates", "description": "Operations with `script_template` table."},
    {"name": "SpecBlockAssociations", "description": "Operations with `spec_block_association` table."},
    {
        "name": "ScriptTemplateAssociations",
        "description": "Operations with `script_template_association` table.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    """Hook FastAPI init/cleanups."""
    # Dependency inits before app starts running
    await db_session_dependency.initialize(config.database_url, config.database_password)
    assert db_session_dependency._engine is not None  # pylint: disable=protected-access
    db_session_dependency._engine.echo = config.database_echo  # pylint: disable=protected-access
    await arq_dependency.initialize(mode=config.arq_mode, redis_settings=config.arq_redis_settings)

    # App runs here...
    yield

    # Dependency cleanups after app is finished
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()


app = FastAPI(
    lifespan=lifespan,
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

app.include_router(productions.router, prefix=config.prefix)
app.include_router(campaigns.router, prefix=config.prefix)
app.include_router(steps.router, prefix=config.prefix)
app.include_router(groups.router, prefix=config.prefix)
app.include_router(jobs.router, prefix=config.prefix)
app.include_router(scripts.router, prefix=config.prefix)

app.include_router(specifications.router, prefix=config.prefix)
app.include_router(spec_blocks.router, prefix=config.prefix)
app.include_router(script_templates.router, prefix=config.prefix)
app.include_router(spec_block_associations.router, prefix=config.prefix)
app.include_router(script_template_associations.router, prefix=config.prefix)

app.include_router(pipetask_error_types.router, prefix=config.prefix)
app.include_router(pipetask_errors.router, prefix=config.prefix)
app.include_router(script_errors.router, prefix=config.prefix)

app.include_router(task_sets.router, prefix=config.prefix)
app.include_router(product_sets.router, prefix=config.prefix)
app.include_router(wms_task_reports.router, prefix=config.prefix)
app.include_router(row.router, prefix=config.prefix)

app.include_router(script_dependencies.router, prefix=config.prefix)
app.include_router(step_dependencies.router, prefix=config.prefix)
app.include_router(queues.router, prefix=config.prefix)
