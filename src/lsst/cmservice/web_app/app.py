import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# from pydantic import BaseModel
from safir.dependencies.db_session import db_session_dependency
from safir.dependencies.http_client import http_client_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.web_app.pages.campaigns import get_campaign_details, search_campaigns
from lsst.cmservice.web_app.pages.group_details import get_group_by_id
from lsst.cmservice.web_app.pages.job_details import get_job_by_id
from lsst.cmservice.web_app.pages.script_details import get_script_by_id
from lsst.cmservice.web_app.pages.step_details import get_step_details_by_id
from lsst.cmservice.web_app.pages.steps import (
    get_campaign_by_id,
    get_campaign_steps,
    get_step_details,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    """Hook FastAPI init/cleanups."""
    # Dependency inits before app starts running
    await db_session_dependency.initialize(config.database_url, config.database_password)
    assert db_session_dependency._engine is not None  # pylint: disable=protected-access
    db_session_dependency._engine.echo = config.database_echo  # pylint: disable=protected-access

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


@web_app.get("/campaigns/", response_class=HTMLResponse)
async def get_campaigns(
    request: Request,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        async with session.begin():
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
            name="pages/campaigns.html",
            request=request,
            context={
                "recent_campaigns": None,
                "productions": production_list,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong:  {e}")


@web_app.post("/campaigns/", response_class=HTMLResponse)
async def search(
    request: Request,
    search_term: Annotated[str, Form()],
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        results = await search_campaigns(session, search_term)
        campaigns_list = []
        for campaign in results:
            campaign_details = await get_campaign_details(session, campaign)
            campaigns_list.append(campaign_details)

        return templates.TemplateResponse(
            "pages/campaign_search_results.html",
            context={
                "search_term": search_term,
                "request": request,
                "search_results": campaigns_list,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong:  {e}")


@web_app.get("/campaign/{campaign_id}/steps/", response_class=HTMLResponse)
async def get_steps(
    request: Request,
    campaign_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        campaign = await get_campaign_by_id(session, campaign_id)
        steps = await get_campaign_steps(session, campaign_id)
        campaign_steps = []
        for step in steps:
            step_details = await get_step_details(session, step)
            campaign_steps.append(step_details)

        return templates.TemplateResponse(
            name="pages/steps.html",
            request=request,
            context={
                "campaign": campaign,
                "steps": campaign_steps,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong {e}")


@web_app.get("/campaign/{campaign_id}/{step_id}/", response_class=HTMLResponse)
async def get_step(
    request: Request,
    campaign_id: int,
    step_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        step, step_groups, step_scripts = await get_step_details_by_id(session, step_id)
        return templates.TemplateResponse(
            name="pages/step_details.html",
            request=request,
            context={
                "campaign_id": campaign_id,
                "step": step,
                "scripts": step_scripts,
                "groups": step_groups,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong {e}")


@web_app.get("/group/{group_id}/", response_class=HTMLResponse)
@web_app.get("/group/{campaign_id}/{step_id}/{group_id}/", response_class=HTMLResponse)
async def get_group(
    request: Request,
    group_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        group_details, jobs, scripts = await get_group_by_id(session, group_id)
        return templates.TemplateResponse(
            name="pages/group_details.html",
            request=request,
            context={
                "group": group_details,
                "jobs": jobs,
                "scripts": scripts,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong {e}")


@web_app.get("/campaign/{campaign_id}/{step_id}/{group_id}/{job_id}/", response_class=HTMLResponse)
async def get_job(
    request: Request,
    campaign_id: int,
    step_id: int,
    group_id: int,
    job_id: int,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        job_details, scripts = await get_job_by_id(session, job_id)
        return templates.TemplateResponse(
            name="pages/job_details.html",
            request=request,
            context={
                "campaign_id": campaign_id,
                "step_id": step_id,
                "group_id": group_id,
                "job": job_details,
                "scripts": scripts,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong {e}")


@web_app.get("/script/{campaign_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{group_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{group_id}/{job_id}/{script_id}/", response_class=HTMLResponse)
async def get_script(
    request: Request,
    script_id: int,
    campaign_id: int | None = None,
    step_id: int | None = None,
    group_id: int | None = None,
    job_id: int | None = None,
    session: async_scoped_session = Depends(db_session_dependency),
) -> HTMLResponse:
    try:
        script_details = await get_script_by_id(
            session,
            script_id=script_id,
            campaign_id=campaign_id,
            step_id=step_id,
            group_id=group_id,
            job_id=job_id,
        )
        return templates.TemplateResponse(
            name="pages/script_details.html",
            request=request,
            context={
                "script": script_details,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb(e.__traceback__)
        return templates.TemplateResponse(f"Something went wrong {e}")


@web_app.get("/layout/", response_class=HTMLResponse)
async def test_layout(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/mockup.html", {"request": request})


@web_app.get("/test-ag-grid/", response_class=HTMLResponse)
async def test_ag_grid(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/test-ag-grid.html", {"request": request})


# NOT WORKING
# @web_app.post("/my-reset-script/", response_class=JSONResponse)
# async def my_reset_script(
#         request: Request,
#         response: Response,
#         # script_id: Annotated[int, Form()],
#         targetStatus: Annotated[str, Form()],
#         session: async_scoped_session = Depends(db_session_dependency)
# ) -> dict:
#     print(f"Resetting script to {targetStatus}")
#     data = {"status": targetStatus}
#     response.status_code = status.HTTP_201_CREATED
#     return data


# WORKING
# class ResetScriptRequest(BaseModel):
#     id: int
#     to_status: int
#
#
# @web_app.post("/my-reset-script/", response_class=JSONResponse)
# async def my_reset_script(request: ResetScriptRequest):
#     # Example response
#     return JSONResponse(
#         content={"id": request.id, "status": request.to_status},
#         status_code=201
#     )
