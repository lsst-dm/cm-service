from pathlib import Path
import traceback
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, Depends
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
from lsst.cmservice.web_app.pages.campaigns import search_campaigns

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
            items = await db.Campaign.get_rows(session)
            production_list = {}
            productions = await db.Production.get_rows(session)
            for p in productions:
                children = await p.children(session)
                production_list[p.name] = children

        return templates.TemplateResponse(
            name="campaigns.html",
            request=request,
            context={
                "recent_campaigns": items,
                "productions": production_list,
            },
        )
    except Exception as e:
        print(e)
        traceback.print_tb()


@web_app.get("/layout/", response_class=HTMLResponse)
async def test_layout(request: Request):
    return templates.TemplateResponse("mockup.html", {"request": request})


@web_app.get("/campaign-search/", response_class=HTMLResponse)
async def search(
    request: Request,
    session: async_scoped_session = Depends(db_session_dependency),
    search_term: str | None = None,
):
    campaigns = await search_campaigns(session, search_term)
    print(campaigns)
    return templates.TemplateResponse("mockup.html", {"request": request})
