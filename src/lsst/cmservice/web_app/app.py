from pathlib import Path
from typing import Annotated
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from lsst.cmservice import db
from safir.dependencies.arq import arq_dependency
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from sqlalchemy.ext.asyncio import async_scoped_session
from safir.logging import configure_logging, configure_uvicorn_logging

from lsst.cmservice.config import config
from lsst.cmservice.web_app.pages.campaigns import search_campaigns, get_campaign_details
from lsst.cmservice.web_app.pages.steps import get_campaign_steps, get_step_details
from lsst.cmservice.web_app.pages.step_details import get_step_details_by_id


configure_logging(profile=config.profile, log_level=config.log_level, name=config.logger_name)
configure_uvicorn_logging(config.log_level)


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


web_app = FastAPI(lifespan=lifespan, title="Campaign Management Tool")

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(Path(BASE_DIR, "templates")))

router = APIRouter(
    prefix="/web_app",
    tags=["Web Application"],
)

web_app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR, "static"))), name="static")


@web_app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@web_app.get("/campaigns/", response_class=HTMLResponse)
async def get_campaigns(request: Request, session: async_scoped_session = Depends(db_session_dependency)):
    try:
        async with session.begin():
            campaigns = await db.Campaign.get_rows(session)
            campaigns_list = []
            for campaign in campaigns:
                campaign_details = await get_campaign_details(session, campaign)
                campaigns_list.append(campaign_details)
            production_list = {}
            productions = await db.Production.get_rows(session)
            for p in productions:
                children = await p.children(session)
                production_campaigns = []
                for c in children:
                    campaign_details = await get_campaign_details(session, c)
                    production_campaigns.append(campaign_details)
                production_list[p.name] = production_campaigns

        return templates.TemplateResponse(
            name="campaigns.html",
            request=request,
            context={
                "recent_campaigns": campaigns_list,
                "productions": production_list,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb()


@web_app.post("/campaigns/", response_class=HTMLResponse)
async def search(
    request: Request,
    search: Annotated[str, Form()],
    session: async_scoped_session = Depends(db_session_dependency),
):
    try:
        results = await search_campaigns(session, search)
        return templates.TemplateResponse(
            "campaign_search_results.html",
            context={
                "request": request,
                "search_results": results,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb()


@web_app.get("/campaign/{campaign_id}/steps/", response_class=HTMLResponse)
async def get_steps(
    request: Request,
    campaign_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
):
    try:
        steps = await get_campaign_steps(session, campaign_id)
        campaign_steps = []
        for step in steps:
            step_details = await get_step_details(session, step)
            campaign_steps.append(step_details)

        return templates.TemplateResponse(
            name="steps.html",
            request=request,
            context={
                "campaign_id": campaign_id,
                "steps": campaign_steps,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb()


@web_app.get("/campaign/{campaign_id}/{step_id}", response_class=HTMLResponse)
async def get_step(
    request: Request,
    step_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
):
    try:
        step, step_groups = await get_step_details_by_id(session, step_id)
        return templates.TemplateResponse(
            name="step_details.html",
            request=request,
            context={
                "step": step,
                "scripts": [
                    {
                        "name": "script name 1",
                        "id": 1,
                    },
                    {
                        "name": "script name 2",
                        "id": 2,
                    },
                ],
                "groups": step_groups,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb()


@web_app.get("/layout/", response_class=HTMLResponse)
async def test_layout(request: Request):
    return templates.TemplateResponse("mockup.html", {"request": request})
