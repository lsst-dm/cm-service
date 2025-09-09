import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from safir.dependencies.http_client import http_client_dependency
from starlette.exceptions import HTTPException as StarletteHTTPException

from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.common.logging import LOGGER
from lsst.cmservice.web_app.pages.campaigns import get_all_campaigns, get_campaign_details, search_campaigns
from lsst.cmservice.web_app.pages.group_details import get_group_by_id
from lsst.cmservice.web_app.pages.job_details import get_job_by_id
from lsst.cmservice.web_app.pages.script_details import get_script_by_id
from lsst.cmservice.web_app.pages.step_details import get_step_details_by_id
from lsst.cmservice.web_app.pages.steps import (
    get_campaign_by_id,
    get_campaign_steps,
    get_step_details,
)
from lsst.cmservice.web_app.utils.utils import (
    get_element,
    update_child_config,
    update_collections,
    update_data_dict,
)

from ..common.types import AnyAsyncSession
from ..db.session import db_session_dependency


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator:
    """Hook FastAPI init/cleanups."""
    # Dependency inits before app starts running
    await db_session_dependency.initialize()
    assert db_session_dependency.engine is not None

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


logger = LOGGER.bind(module=__name__)

web_app.mount("/static", StaticFiles(directory=str(Path(BASE_DIR, "static"))), name="static")

logger.info("Starting web app...")


@web_app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    logger.error("HTTP Error", extra=dict(url=request.url), code=exc.status_code, detail=exc.detail)

    is_json_request = (
        "application/json" in request.headers.get("accept", "")
        or request.url.path.startswith("/web_app/api")
        or request.url.path.startswith("/cm-service")
    )

    is_htmx = request.headers.get("HX-Request") == "true"

    if is_json_request and not is_htmx:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # if it's a htmx request, add the HX-Redirect header
    # to the response to redirect to the error page and
    # avoid swapping response within the page
    if is_htmx:
        if exc.status_code == 404:
            response = HTMLResponse("<div>Content not found</div>", status_code=404)
        elif exc.status_code < 500:
            response = HTMLResponse(f"<div>{exc.detail}</div>", status_code=exc.status_code)
        else:
            redirect_url = request.url_for("error_page", error_code=exc.status_code)
            response = HTMLResponse("", status_code=exc.status_code)
            response.headers["HX-Redirect"] = redirect_url.path

        return response

    return templates.TemplateResponse(
        "pages/error.html", {"request": request, "status_code": exc.status_code, "detail": exc.detail}
    )


@web_app.get("/campaigns/", response_class=HTMLResponse)
async def get_campaigns(
    request: Request,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> HTMLResponse:
    try:
        campaign_list = []
        async with session.begin():
            campaigns = await get_all_campaigns(session)
            for campaign in campaigns:
                campaign_details = await get_campaign_details(session, campaign)
                campaign_list.append(campaign_details)

        return templates.TemplateResponse(
            name="pages/campaigns.html",
            request=request,
            context={
                "recent_campaigns": None,
                "all_campaigns": campaign_list,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting campaigns: {e}")


@web_app.post("/campaigns/", response_class=HTMLResponse)
async def search(
    request: Request,
    search_term: Annotated[str, Form()],
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
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
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error searching campaigns: {e}")


@web_app.get("/campaign/{campaign_id}/steps/", response_class=HTMLResponse)
async def get_steps(
    request: Request,
    campaign_id: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> HTMLResponse:
    try:
        campaign = await get_campaign_by_id(session, campaign_id)
        if campaign is None:
            msg = f"Campaign {campaign_id} not found!"
            raise Exception(msg)
        campaign_details = await get_campaign_details(session, campaign)
        steps = await get_campaign_steps(session, campaign_id)
        campaign_steps = []
        for step in steps:
            step_details = await get_step_details(session, step)
            campaign_steps.append(step_details)

        return templates.TemplateResponse(
            name="pages/steps.html",
            request=request,
            context={
                "campaign": campaign_details,
                "steps": campaign_steps,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting steps: {e}")


@web_app.get("/campaign/{campaign_id}/{step_id}/", response_class=HTMLResponse)
async def get_step(
    request: Request,
    campaign_id: int,
    step_id: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
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
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting step details: {e}")


@web_app.get("/group/{group_id}/", response_class=HTMLResponse)
@web_app.get("/group/{campaign_id}/{step_id}/{group_id}/", response_class=HTMLResponse)
async def get_group(
    request: Request,
    group_id: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
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
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting group details: {e}")


@web_app.get("/campaign/{campaign_id}/{step_id}/{group_id}/{job_id}/", response_class=HTMLResponse)
async def get_job(
    request: Request,
    campaign_id: int,
    step_id: int,
    group_id: int,
    job_id: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
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
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting job details: {e}")


@web_app.get("/script/{campaign_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{group_id}/{script_id}/", response_class=HTMLResponse)
@web_app.get("/script/{campaign_id}/{step_id}/{group_id}/{job_id}/{script_id}/", response_class=HTMLResponse)
async def get_script(
    request: Request,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
    script_id: int,
    campaign_id: int | None = None,
    step_id: int | None = None,
    group_id: int | None = None,
    job_id: int | None = None,
) -> HTMLResponse:
    try:
        script_details = await get_script_by_id(
            session,
            script_id=script_id,
            campaign_id=campaign_id,
            step_id=step_id,
            group_id=group_id,
            job_id=job_id,
            request=request,
        )
        return templates.TemplateResponse(
            name="pages/script_details.html",
            request=request,
            context={
                "script": script_details,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error getting script details: {e}")


@web_app.get("/layout/", response_class=HTMLResponse)
async def test_layout(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pages/mockup.html", {"request": request})


class ReadScriptLogRequest(BaseModel):
    log_path: str


@web_app.post("/api/read-script-log")
async def read_script_log(request: ReadScriptLogRequest) -> dict[str, str]:
    file_path = Path(request.log_path)

    # Check if the file exists
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: \n{file_path}")

    try:
        # Read the content of the file
        content = file_path.read_text()
        return {"content": content}
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error reading log file: {e}. \n{file_path}")


@web_app.post("/update-collections/{element_type}/{element_id}", response_class=HTMLResponse)
async def update_element_collections(
    request: Request,
    element_id: int,
    element_type: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> HTMLResponse:
    try:
        element = await get_element(session, element_id, element_type)
        if element is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Error updating collections: {LevelEnum(element_type).name} {element_id} Not Found!!",
            )
        collections = await request.form()
        collection_dict = {key: value for key, value in collections.items()}
        updated_element = await update_collections(
            session=session, element=element, collections=collection_dict
        )
        return templates.TemplateResponse(
            name="partials/edit_collections_response.html",
            request=request,
            context={
                "element": updated_element,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error updating collections: {e}")


@web_app.post("/update-child-config/{element_type}/{element_id}", response_class=HTMLResponse)
async def update_element_child_config(
    request: Request,
    element_id: int,
    element_type: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> HTMLResponse:
    try:
        element = await get_element(session, element_id, element_type)
        if element is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Error updating child config: "
                f"{LevelEnum(element_type).name} {element_id} Not Found!!",
            )
        child_config = await request.form()
        child_config_dict = {key: value for key, value in child_config.items()}
        updated_element = await update_child_config(
            session=session, element=element, child_config=child_config_dict
        )
        return templates.TemplateResponse(
            name="partials/edit_child_config_response.html",
            request=request,
            context={
                "element": updated_element,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error updating child config: {e}")


@web_app.post("/update-data-dict/{element_type}/{element_id}", response_class=HTMLResponse)
async def update_element_data_dict(
    request: Request,
    element_id: int,
    element_type: int,
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
) -> HTMLResponse:
    try:
        element = await get_element(session, element_id, element_type)
        if element is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"Error updating data dict: {LevelEnum(element_type).name} {element_id} Not Found!!",
            )
        data = await request.form()
        data_dict = {key: value for key, value in data.items()}
        updated_element = await update_data_dict(session=session, element=element, data_dict=data_dict)
        return templates.TemplateResponse(
            name="partials/edit_data_dict_response.html",
            request=request,
            context={
                "element": updated_element,
            },
        )
    except Exception as e:
        traceback.print_tb(e.__traceback__)
        raise HTTPException(status_code=500, detail=f"Error updating data dict: {e}")


@web_app.post("/collections/{element_id}/{element_type}/update")
async def update_collections_htmx(
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
    element_id: int,
    element_type: int,
    request: Request,
    keys: Annotated[list[str], Form()],
    values: Annotated[list[str], Form()],
    new_keys: Annotated[list[str], Form()] = [],
    new_values: Annotated[list[str], Form()] = [],
) -> HTMLResponse:
    element = await get_element(session, element_id, element_type)
    if element is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Error updating data dict: {LevelEnum(element_type).name} {element_id} Not Found!!",
        )

    collection_dict = {}
    for key, value in zip(keys, values):
        key = key.strip()
        if key:
            collection_dict[key] = value

    for key, value in zip(new_keys, new_values):
        key = key.strip()
        if key:
            collection_dict[key] = value

    updated_element = await update_collections(session=session, element=element, collections=collection_dict)

    return templates.TemplateResponse(
        name="partials/edit_collections_response.html",
        request=request,
        context={
            "element": updated_element,
        },
    )


@web_app.post("/collections/{element_id}/{element_type}/add-field")
@web_app.post("/data-dict/{element_id}/{element_type}/add-field")
@web_app.post("/child-config/{element_id}/{element_type}/add-field")
async def add_collection_field(
    element_id: int,
    element_type: int,
    request: Request,
) -> HTMLResponse:
    import uuid

    field_id = str(uuid.uuid4())[:8]

    return templates.TemplateResponse(
        name="partials/new_field.html",
        request=request,
        context={"element_id": element_id, "field_id": field_id, "element_type": element_type},
    )


@web_app.post("/collections/{element_id}/{element_type}/remove-new-field/{field_id}")
@web_app.post("/data-dict/{element_id}/{element_type}/remove-new-field/{field_id}")
@web_app.post("/child-config/{element_id}/{element_type}/remove-new-field/{field_id}")
async def remove_new_field(element_id: int, element_type: int, field_id: str) -> str:
    # This just returns empty content to remove the field from DOM
    return ""


@web_app.post("/data-dict/{element_id}/{element_type}/update")
async def update_data_dict_htmx(
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
    element_id: int,
    element_type: int,
    request: Request,
    keys: Annotated[list[str], Form()] = [],
    values: Annotated[list[str], Form()] = [],
    new_keys: Annotated[list[str], Form()] = [],
    new_values: Annotated[list[str], Form()] = [],
) -> HTMLResponse:
    element = await get_element(session, element_id, element_type)
    if element is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Error updating data dict: {LevelEnum(element_type).name} {element_id} Not Found!!",
        )

    data_dict = {}
    for key, value in zip(keys, values):
        key = key.strip()
        if key:
            data_dict[key] = value

    for key, value in zip(new_keys, new_values):
        key = key.strip()
        if key:
            data_dict[key] = value

    updated_element = await update_data_dict(session=session, element=element, data_dict=data_dict)

    return templates.TemplateResponse(
        name="partials/edit_data_dict_response.html",
        request=request,
        context={
            "element": updated_element,
        },
    )


@web_app.post("/child-config/{element_id}/{element_type}/update")
async def update_child_config_htmx(
    session: Annotated[AnyAsyncSession, Depends(db_session_dependency)],
    element_id: int,
    element_type: int,
    request: Request,
    keys: Annotated[list[str], Form()] = [],
    values: Annotated[list[str], Form()] = [],
    new_keys: Annotated[list[str], Form()] = [],
    new_values: Annotated[list[str], Form()] = [],
) -> HTMLResponse:
    element = await get_element(session, element_id, element_type)
    if element is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Error updating child config: {LevelEnum(element_type).name} {element_id} Not Found!!",
        )

    child_config = {}
    for key, value in zip(keys, values):
        key = key.strip()
        if key:
            child_config[key] = value

    for key, value in zip(new_keys, new_values):
        key = key.strip()
        if key:
            child_config[key] = value

    updated_element = await update_child_config(session=session, element=element, child_config=child_config)

    return templates.TemplateResponse(
        name="partials/edit_child_config_response.html",
        request=request,
        context={
            "element": updated_element,
        },
    )
