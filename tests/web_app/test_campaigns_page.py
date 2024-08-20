import re
import pytest
from unittest.mock import Mock

from playwright.sync_api import expect, sync_playwright

from lsst.cmservice import db
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.db import Campaign, Production
from lsst.cmservice.web_app.pages.campaigns import get_campaign_details


@pytest.fixture()
def mock_session():
    yield Mock()


@pytest.fixture()
def first_production():
    return Production(
        id=1,
        name="first_production",
    )


@pytest.fixture()
def mock_collections():
    return {
        "collection_1": "collection 1",
        "collection_2": "collection 2",
        "collection_3": "collection 3",
        "out": "output_path",
    }


@pytest.fixture()
def mock_scripts():
    return [
        db.Script(id=1, name="first_script", status=StatusEnum.accepted),
        db.Script(id=2, name="second_script", status=StatusEnum.accepted),
    ]


@pytest.fixture()
def first_campaign(monkeypatch, mock_collections, mock_scripts, mock_session):
    campaign = Campaign(
        id=1,
        name="first_campaign",
        parent_id=1,
        fullname="first_production/first_campaign",
        spec_id=1,
        spec_block_id=1,
        data={"lsst_version": "lsst_version_1"},
        status=StatusEnum.accepted,
    )

    async def mock_resolve_collections(mock_session):
        return mock_collections

    async def mock_get_all_scripts(mock_session):
        return mock_scripts

    monkeypatch.setattr(campaign, "resolve_collections", mock_resolve_collections)
    monkeypatch.setattr(campaign, "get_all_scripts", mock_get_all_scripts)
    return campaign


@pytest.fixture()
def mock_groups():
    yield [
        db.Group(id=1, name="first_group", status=StatusEnum.accepted),
        db.Group(id=1, name="second_group", status=StatusEnum.accepted),
    ]


@pytest.fixture()
def mock_campaign_groups(mock_session, first_campaign, mock_groups):
    async def mock_get_all_groups(mock_session, first_campaign):
        return mock_groups

    return mock_get_all_groups


@pytest.mark.asyncio
async def test_get_campaign_details(first_campaign, monkeypatch, mock_session, mock_campaign_groups):
    monkeypatch.setattr("lsst.cmservice.web_app.pages.campaigns.get_campaign_groups", mock_campaign_groups)
    campaign_details = await get_campaign_details(mock_session, first_campaign)
    assert isinstance(campaign_details, dict)
    assert campaign_details == {
        "id": 1,
        "name": "first_campaign",
        "lsst_version": "lsst_version_1",
        "out": "output_path",
        "source": "",
        "status": "COMPLETE",
        "groups_completed": "2 of 2 groups completed",
        "scripts_completed": "2 of 2 scripts completed",
        "need_attention_groups": [],
        "need_attention_scripts": [],
    }


def test_campaigns_page() -> None:
    with sync_playwright() as playwright:
        my_browser = playwright.chromium.launch(headless=False)
        context = my_browser.new_context()
        # context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        # load campaigns page
        page.goto("http://0.0.0.0:8080/web_app/campaigns/")
        # check number of campaigns with name 'test_panda'
        expect(page.get_by_title("test_panda")).to_have_count(8)
        # check number of campaigns with name 'test_htcondor'
        expect(page.get_by_title("test_htcondor")).to_have_count(8)
        # check number of campaigns in the page
        expect(page.locator(".campaign-card")).to_have_count(16)
        # check page title
        expect(page).to_have_title(re.compile("Campaigns"))
        # check first campaign to be completed
        expect(
            page.locator(".campaign-card").first.filter(
                has=page.locator(".text-green-400"),
            ),
        ).to_have_count(1)
        # check second campaign to be in progress
        expect(
            page.locator(".campaign-card")
            .nth(1)
            .filter(
                has=page.locator(".text-cyan-400"),
            ),
        ).to_have_count(1)
        # check second campaign (using a different locator) to be in progress
        expect(
            page.locator(".campaign-card")
            .filter(has=page.get_by_text("test_htcondor"))
            .first.filter(has=page.locator(".text-cyan-400")),
        ).to_have_count(1)
        # click the first campaign details link
        page.get_by_title("test_panda").first.click(force=True)
        # check navigation to step list page
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/1/steps/")
        # check correct campaign name
        expect(page.get_by_text("test_panda", exact=True)).not_to_be_empty()
        # check production name
        expect(page.get_by_role("link", name="HSC_DRP-Prod")).not_to_be_empty()
        # click breadcrumbs
        page.get_by_role("link", name="HSC_DRP-Prod").click()
        # make sure it goes back to campaigns page
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        # check production 'HSC_DRP-Prod' exists
        expect(page.get_by_role("heading", name="HSC_DRP-Prod")).not_to_be_empty()
        # search campaigns for 'test_panda'
        page.get_by_placeholder("Search Campaigns").fill("test_panda")
        page.get_by_placeholder("Search Campaigns").press("Enter")
        # display search term in search results page
        page.get_by_role("heading", name="Search results for: test_panda")
        # check search results count
        expect(page.get_by_title("test_panda")).to_have_count(8)
        # make sure clicking the logo navigates to campaigns page
        page.get_by_role("link", name="Rubin").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        # context.tracing.stop(path="trace2.zip")
        context.close()
        my_browser.close()


# @pytest.fixture()
# def mock_campaigns():
#     return {
#         "recent_campaigns": [
#             {
#                 "id": 1,
#                 "name": "campaign1",
#                 "lsst_version": "lsst_version",
#                 "out": "out",
#                 "source": "campaign_source",
#                 "status": "status",
#                 "groups_completed": "1 of 1 groups completed",
#                 "scripts_completed": "1 of 1 scripts completed",
#                 "need_attention_groups": None,
#                 "need_attention_scripts": None,
#             }
#
#         ],
#         "productions": {
#             "production1": [
#                     {
#                         "id": 1,
#                         "name": "campaign1",
#                         "lsst_version": "lsst_version",
#                         "out": "out",
#                         "source": "campaign_source",
#                         "status": "status",
#                         "groups_completed": "1 of 1 groups completed",
#                         "scripts_completed": "1 of 1 scripts completed",
#                         "need_attention_groups": None,
#                         "need_attention_scripts": None,
#                     }
#                 ]
#             }
#     }


# @pytest.mark.asyncio()
# async def test_has_title(uvicorn: UvicornProcess) -> None:
#     async with async_playwright() as playwright:
#         my_browser = await playwright.chromium.launch(headless=False)
#         my_page = await my_browser.new_page()
#         await my_page.goto(f"{uvicorn.url}/web_app/campaigns/")
#         await expect(my_page).to_have_title(re.compile("Campaigns"))
#         time.sleep(10)
#         await my_browser.close()


# @pytest.mark.asyncio()
# async def test_has_description(webapp_uvicorn, app, engine):
#     # logger = structlog.get_logger(config.logger_name)
#     # the_engine =
#     create_database_engine(config.database_url, config.database_password)
#     # await initialize_database(
#     the_engine, logger, schema=db.Base.metadata, reset=True)
#     #
#     # # async with LifespanManager(main.app):
#     # #     yield main.app
#     #
#     # my_uvicorn = spawn_uvicorn(
#     #     working_directory=tmp_path_factory.mktemp("uvicorn"),
#     #     # app="lsst.cmservice.main:app",
#     #     factory=main.app,
#     #     timeout=10,
#     # )
#
#     async with async_playwright() as playwright:
#         my_browser = await playwright.chromium.launch(headless=False)
#         my_page = await my_browser.new_page()
#         await my_page.goto(f"{webapp_uvicorn.url}/web_app/campaigns/")
#         await expect(my_page).to_have_title(re.compile("Campaigns"))
#         time.sleep(10)
#         await my_browser.close()

# def test_playwright_fixtures(page):
#     page.goto("http://0.0.0.0:8080/web_app/campaigns/")
#     assert True
