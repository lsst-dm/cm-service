from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging, configure_uvicorn_logging
from safir.middleware.x_forwarded import XForwardedMiddleware

from . import __version__
from .config import config
from .routers import (
    actions,
    campaigns,
    groups,
    healthz,
    index,
    jobs,
    loaders,
    pipetask_error_types,
    pipetask_errors,
    product_sets,
    productions,
    queues,
    script_dependencies,
    script_errors,
    script_templates,
    scripts,
    spec_blocks,
    specifications,
    step_dependencies,
    steps,
    task_sets,
    wms_task_reports,
)
from .web_app import web_app

configure_uvicorn_logging(config.logging.level)
configure_logging(profile=config.logging.profile, log_level=config.logging.level, name=config.asgi.title)

tags_metadata = [
    {
        "name": "Loaders",
        "description": "Operations that load Objects in to the DB.",
    },
    {
        "name": "Actions",
        "description": "Operations perform actions on existing Objects in to the DB."
        "In many cases this will result in the creating of new objects in the DB.",
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
    {"name": "Specifications", "description": "Operations with `specification` table."},
    {"name": "SpecBlocks", "description": "Operations with `spec_block` table."},
    {"name": "ScriptTemplates", "description": "Operations with `script_template` table."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Hook FastAPI init/cleanups."""
    app.state.tasks = set()
    # Dependency inits before app starts running
    await db_session_dependency.initialize(config.db.url, config.db.password)
    assert db_session_dependency._engine is not None
    db_session_dependency._engine.echo = config.db.echo

    # App runs here...
    yield

    # Dependency cleanups after app is finished
    await db_session_dependency.aclose()
    await http_client_dependency.aclose()


app = FastAPI(
    lifespan=lifespan,
    title=config.asgi.title,
    version=__version__,
    openapi_url=f"{config.asgi.prefix}/openapi.json",
    openapi_tags=tags_metadata,
    docs_url=f"{config.asgi.prefix}/docs",
    redoc_url=f"{config.asgi.prefix}/redoc",
)

app.add_middleware(XForwardedMiddleware)

app.include_router(healthz.health_router)
app.include_router(index.router)
app.include_router(loaders.router, prefix=config.asgi.prefix)
app.include_router(actions.router, prefix=config.asgi.prefix)

app.include_router(productions.router, prefix=config.asgi.prefix)
app.include_router(campaigns.router, prefix=config.asgi.prefix)
app.include_router(steps.router, prefix=config.asgi.prefix)
app.include_router(groups.router, prefix=config.asgi.prefix)
app.include_router(jobs.router, prefix=config.asgi.prefix)
app.include_router(scripts.router, prefix=config.asgi.prefix)

app.include_router(specifications.router, prefix=config.asgi.prefix)
app.include_router(spec_blocks.router, prefix=config.asgi.prefix)
app.include_router(script_templates.router, prefix=config.asgi.prefix)

app.include_router(pipetask_error_types.router, prefix=config.asgi.prefix)
app.include_router(pipetask_errors.router, prefix=config.asgi.prefix)
app.include_router(script_errors.router, prefix=config.asgi.prefix)

app.include_router(task_sets.router, prefix=config.asgi.prefix)
app.include_router(product_sets.router, prefix=config.asgi.prefix)
app.include_router(wms_task_reports.router, prefix=config.asgi.prefix)

app.include_router(script_dependencies.router, prefix=config.asgi.prefix)
app.include_router(step_dependencies.router, prefix=config.asgi.prefix)
app.include_router(queues.router, prefix=config.asgi.prefix)

# Start the frontend web application.
app.mount(config.asgi.frontend_prefix, web_app)


if __name__ == "__main__":
    uvicorn.run(
        "lsst.cmservice.main:app", host=config.asgi.host, port=config.asgi.port, reload=config.asgi.reload
    )
