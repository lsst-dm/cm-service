import typing
from unittest.mock import Mock

import pytest
from _pytest.monkeypatch import MonkeyPatch
from playwright.sync_api import expect, sync_playwright

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.db import Step
from lsst.cmservice.web_app.pages.steps import get_step_details


@pytest.fixture()
def mock_session() -> typing.Generator:
    yield Mock()


@pytest.fixture()
def mock_step() -> Step:
    step = Step(
        id=1,
        name="first_step",
        parent_id=1,
        fullname="first_production/first_campaign/first_step",
        status=StatusEnum.accepted,
    )
    return step


@pytest.fixture()
def mock_groups() -> typing.Generator:
    yield [
        db.Group(id=1, name="first_group", status=StatusEnum.accepted),
        db.Group(id=2, name="second_group", status=StatusEnum.paused),
        db.Group(id=3, name="third_group", status=StatusEnum.failed),
        db.Group(id=4, name="fourth_group", status=StatusEnum.rejected),
    ]


@pytest.mark.asyncio
async def test_get_step_details(
    mock_step: Step,
    monkeypatch: MonkeyPatch,
    mock_session: Mock,
    mock_groups: list,
) -> None:
    async def mock_children(mock_session: Mock) -> list:
        return mock_groups

    monkeypatch.setattr(mock_step, "children", mock_children)
    step_details = await get_step_details(mock_session, mock_step)
    assert isinstance(step_details, dict)
    assert step_details == {
        "id": 1,
        "name": "first_step",
        "fullname": "first_production/first_campaign/first_step",
        "status": "COMPLETE",
        "no_groups": 4,
        "no_groups_completed": 1,
        "no_groups_need_attention": 1,
        "no_groups_failed": 2,
        "level": LevelEnum.step.value,
    }


@pytest.mark.playwright
def test_steps_page() -> None:
    with sync_playwright() as playwright:
        my_browser = playwright.chromium.launch(headless=False)
        context = my_browser.new_context()
        # context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        # navigate to step list of the first campaign
        page.goto("http://0.0.0.0:8080/web_app/campaign/4/steps/")
        # check 1st step fullname is correct
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_26_DM-45061/step1")).not_to_be_empty()
        # check number of groups is right
        expect(page.get_by_text("6 Group(s)")).not_to_be_empty()
        # check the campaign has 12 steps
        expect(page.locator(".step-card")).to_have_count(14)
        # check the first step card has a full width progress bar with green bg
        expect(page.locator(".step-card").first.filter(has=page.locator(".bg-green-500"))).not_to_be_empty()
        expect(page.locator(".bg-green-500").first).to_have_attribute("style", "width: 101%")
        # check campaign name is correct
        expect(page.get_by_text("w_2024_26_DM-45061", exact=True)).not_to_be_empty()
        # check clicking the first step name opens step details page
        page.get_by_role("link", name="step1", exact=True).click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/4/29/")
        # check clicking campaign name breadcrumb
        # in step details opens step list page
        page.get_by_role("link", name="w_2024_26_DM-45061").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/4/steps/")
        # check clicking production name opens campaigns page
        page.get_by_role("link", name="HSC_DRP-RC2", exact=True).click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaigns/")
        # context.tracing.stop(path="trace2.zip")
        context.close()
        my_browser.close()
