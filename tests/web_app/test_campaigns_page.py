import re
import typing
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from playwright.sync_api import expect, sync_playwright

from lsst.cmservice import db
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.db import Campaign
from lsst.cmservice.web_app.pages.campaigns import get_campaign_details


@pytest.fixture()
def mock_session() -> typing.Generator:
    yield Mock()


@pytest.fixture()
def mock_collections() -> dict:
    return {
        "collection_1": "collection 1",
        "collection_2": "collection 2",
        "collection_3": "collection 3",
        "out": "output_path",
    }


@pytest.fixture()
def mock_scripts() -> list:
    return [
        db.Script(id=1, name="first_script", status=StatusEnum.accepted),
        db.Script(id=2, name="second_script", status=StatusEnum.accepted),
    ]


@pytest.fixture()
def first_campaign(
    monkeypatch: MonkeyPatch,
    mock_collections: dict,
    mock_scripts: list,
    mock_session: Mock,
) -> Campaign:
    campaign = Campaign(
        id=1,
        name="first_campaign",
        fullname="first_production/first_campaign",
        spec_id=1,
        spec_block_id=1,
        data={"lsst_version": "lsst_version_1"},
        status=StatusEnum.accepted,
        metadata_={"crtime": 946684800},
    )

    async def mock_resolve_collections(mock_session: Mock, *, throw_overrides: bool) -> dict:
        return mock_collections

    async def mock_get_all_scripts(mock_session: Mock) -> list:
        return mock_scripts

    monkeypatch.setattr(campaign, "resolve_collections", mock_resolve_collections)
    monkeypatch.setattr(campaign, "get_all_scripts", mock_get_all_scripts)
    return campaign


@pytest.fixture()
def mock_groups() -> typing.Generator:
    yield [
        db.Group(id=1, name="first_group", status=StatusEnum.accepted),
        db.Group(id=1, name="second_group", status=StatusEnum.accepted),
    ]


@pytest.fixture()
def mock_steps() -> typing.Generator:
    yield []


@pytest.fixture()
def mock_step_detail() -> typing.Generator:
    yield {}


@pytest.fixture()
def mock_campaign_groups(
    mock_session: Mock,
    first_campaign: Campaign,
    mock_groups: typing.Callable,
) -> typing.Callable:
    async def mock_get_all_groups(mock_session: Mock, first_campaign: Campaign) -> typing.Callable:
        return mock_groups

    return mock_get_all_groups


@pytest.fixture()
def mock_campaign_steps(
    mock_session: Mock,
    first_campaign: Campaign,
    mock_steps: typing.Callable,
) -> typing.Callable:
    async def mock_get_all_steps(mock_session: Mock, first_campaign: Campaign) -> typing.Callable:
        return mock_steps

    return mock_get_all_steps


@pytest.fixture()
def mock_step_details(
    mock_session: Mock,
    first_campaign: Campaign,
    mock_steps: typing.Callable,
) -> typing.Callable:
    async def mock_get_step_detail(mock_session: Mock, first_campaign: Campaign) -> typing.Callable:
        return mock_step_detail

    return mock_get_step_detail


@pytest.mark.asyncio
async def test_get_campaign_details(
    first_campaign: Campaign,
    monkeypatch: MonkeyPatch,
    mock_session: Mock,
    mock_campaign_groups: typing.Callable,
    mock_campaign_steps: typing.Callable,
    mock_step_details: typing.Callable,
) -> None:
    monkeypatch.setattr("lsst.cmservice.web_app.pages.campaigns.get_campaign_groups", mock_campaign_groups)
    monkeypatch.setattr("lsst.cmservice.web_app.pages.campaigns.get_campaign_steps", mock_campaign_steps)
    monkeypatch.setattr("lsst.cmservice.web_app.pages.campaigns.get_step_details", mock_step_details)
    campaign_details = await get_campaign_details(mock_session, first_campaign)
    assert isinstance(campaign_details, dict)
    assert campaign_details == {
        "id": 1,
        "name": "first_campaign",
        "lsst_version": "lsst_version_1",
        "source": "",
        "status": "COMPLETE",
        "complete_steps": [],
        "in_progress_steps": [],
        "need_attention_steps": [],
        "need_attention_groups": [],
        "need_attention_scripts": [],
        "child_config": None,
        "collections": {
            "collection_1": "collection 1",
            "collection_2": "collection 2",
            "collection_3": "collection 3",
            "out": "output_path",
        },
        "data": {
            "lsst_version": "lsst_version_1",
        },
        "level": 1,
        "last_updated": "2000-01-01T00:00:00Z",
        "org_status": {"name": "accepted", "value": 5},
    }


@pytest.mark.playwright
def test_campaigns_page() -> None:
    with sync_playwright() as playwright:
        my_browser = playwright.chromium.launch(headless=False)
        context = my_browser.new_context()
        page = context.new_page()
        # load campaigns page
        page.goto("http://0.0.0.0:8080/web_app/campaigns/")
        # check number of campaigns in the page
        expect(page.locator(".campaign-card")).to_have_count(13)
        # check page title
        expect(page).to_have_title(re.compile("Campaigns"))
        # check fourth campaign to be completed
        expect(
            page.locator(".campaign-card").nth(3).locator(".text-green-400"),
        ).to_have_count(1)
        # click the first campaign details link
        page.get_by_title("w_2024_26_DM-45061", exact=True).click(force=True)
        # check navigation to step list page
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/4/steps/")
        # check correct campaign name
        expect(page.get_by_text("w_2024_26_DM-45061", exact=True)).not_to_be_empty()
        # check production name
        expect(page.get_by_role("link", name="HSC_DRP-RC2", exact=True)).not_to_be_empty()
        # click breadcrumbs
        page.get_by_role("link", name="HSC_DRP-RC2", exact=True).click()
        # make sure it goes back to campaigns page
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        # check production 'HSC_DRP-RC2' exists
        expect(page.get_by_role("heading", name="HSC_DRP-RC2")).not_to_be_empty()
        # search campaigns for 'test_panda'
        page.get_by_placeholder("Search Campaigns").fill("w_2024_30_DM-45425")
        page.get_by_placeholder("Search Campaigns").press("Enter")
        # display search term in search results page
        expect(page.get_by_role("heading", name="Search results for: w_2024_30_DM-45425")).not_to_be_empty()
        # check search results count
        expect(page.locator(".campaign-card")).to_have_count(4)
        # check failing script link
        expect(page.get_by_role("link", name="manifest_report")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/script/16/710/",
        )
        # click failing script link
        page.get_by_role("link", name="manifest_report").click()
        # check breadcrumbs are correct
        expect(page.get_by_role("link", name="job_000")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/16/157/94/94/",
        )
        expect(page.get_by_role("link", name="group1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/group/16/157/94/",
        )
        expect(page.get_by_role("link", name="step1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/16/157/",
        )
        expect(page.get_by_role("link", name="w_2024_30_DM-45425b")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/16/steps/",
        )
        expect(page.get_by_role("link", name="HSC_DRP-RC2")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaigns/",
        )
        # make sure clicking the logo navigates to campaigns page
        page.get_by_role("link", name="Rubin").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        context.close()
        my_browser.close()
