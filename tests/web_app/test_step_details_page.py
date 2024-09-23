import os
import uuid

import pytest
import structlog
from playwright.sync_api import expect, sync_playwright
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.web_app.pages.step_details import get_step_details_by_id
from tests.db.util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_get_step_details_by_id(engine: AsyncEngine) -> None:
    """Test `web_app.pages.step_details.get_step_details_by_id`
    function."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.group, uuid_int)

        step, step_groups, step_scripts = await get_step_details_by_id(session, 1)
        assert len(step_scripts) == 0
        assert len(step_groups) == 5

        assert step == {
            "id": 1,
            "name": f"step0_{uuid_int}",
            "fullname": f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}",
            "status": "IN_PROGRESS",
            "no_groups": 5,
            "no_groups_completed": 0,
            "no_groups_need_attention": 0,
            "no_groups_failed": 0,
            "child_config": {},
            "collections": {
                "step_input": f"cm/hsc_rc2_micro/step0_{uuid_int}/input",
                "step_output": f"cm/hsc_rc2_micro/step0_{uuid_int}_ouput",
                "step_public_output": f"cm/hsc_rc2_micro/step0_{uuid_int}",
                "step_validation": f"cm/hsc_rc2_micro/step0_{uuid_int}/validate",
            },
            "data": {},
        }

        assert step_groups == [
            {
                "id": 1,
                "name": f"group0_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": {},
                "child_config": {},
                "spec_aliases": {},
            },
            {
                "id": 2,
                "name": f"group1_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": {},
                "child_config": {},
                "spec_aliases": {},
            },
            {
                "id": 3,
                "name": f"group2_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": {},
                "child_config": {},
                "spec_aliases": {},
            },
            {
                "id": 4,
                "name": f"group3_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": {},
                "child_config": {},
                "spec_aliases": {},
            },
            {
                "id": 5,
                "name": f"group4_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": {},
                "child_config": {},
                "spec_aliases": {},
            },
        ]

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.close()
        await session.remove()


@pytest.mark.playwright
def test_step_details_page() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        # open step details page
        page.goto("http://0.0.0.0:8080/web_app/campaign/17/171/")
        # check step name is correct
        expect(page.get_by_text("step1", exact=True)).not_to_be_empty()
        # check step fullname is correct
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1")).not_to_be_empty()
        # check collections section
        expect(page.get_by_text("Collections").first).not_to_be_empty()
        # check collections are correct
        expect(page.get_by_text("step_input: HSC/runs/RC2/w_2024_30/DM-45425c/step1/input")).not_to_be_empty()
        expect(
            page.get_by_text("step_output: HSC/runs/RC2/w_2024_30/DM-45425c/step1_ouput"),
        ).not_to_be_empty()
        expect(
            page.get_by_text("step_public_output: HSC/runs/RC2/w_2024_30/DM-45425c/step1"),
        ).not_to_be_empty()
        expect(
            page.get_by_text("step_validation: HSC/runs/RC2/w_2024_30/DM-45425c/step1/validate"),
        ).not_to_be_empty()
        # check child config section exists
        expect(page.get_by_text("Child Config")).not_to_be_empty()
        # check child config values are correct
        expect(page.get_by_text("split_method: split_by_query")).not_to_be_empty()
        expect(page.get_by_text("split_min_groups: 5")).not_to_be_empty()
        # check number of groups are correct
        expect(page.get_by_text("6 Groups")).to_be_visible()
        # check groups progress is showing
        expect(page.locator(".bg-green-500")).to_be_visible()
        # check scripts grid exists
        expect(page.locator("#scriptsGrid")).to_be_visible()
        # check number of step scripts (4 scripts + 1 header row)
        expect(page.locator("#scriptsGrid").get_by_role("row")).to_have_count(5)
        # click on "make_step_public_output" script
        page.get_by_role("link", name="make_step_public_output").click()
        # check that script details page is open and has the correct values
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/script/17/171/721/")
        expect(page.get_by_text("make_step_public_output", exact=True)).to_be_visible()
        expect(
            page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/make_step_public_output_000"),
        ).to_be_visible()
        # back to step details page
        page.goto("http://0.0.0.0:8080/web_app/campaign/17/171/")
        # check groups grid exists
        expect(page.locator("#groupsGrid")).to_be_visible()
        # check number of step groups (6 groups + 1 header row)
        expect(page.locator("#groupsGrid").get_by_role("row")).to_have_count(7)
        # check first Data column value
        expect(
            page.get_by_role(
                "gridcell",
                name="instrument='HSC' and skymap='hsc_rings_v1' AND (38944 <= exposure)",
            ),
        ).to_be_visible()
        # click "group0"
        page.get_by_role("link", name="group0").click()
        # check group details page is open and correct values displayed
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/group/17/171/95/")
        expect(page.get_by_text("group0", exact=True)).to_be_visible()
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/group0")).to_be_visible()
        context.close()
        browser.close()
