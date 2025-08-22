import os
import uuid

import pytest
import structlog
from httpx import AsyncClient
from playwright.sync_api import expect, sync_playwright
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.api.web_app.pages.step_details import get_step_details_by_id
from lsst.cmservice.core import db
from lsst.cmservice.core.common.enums import LevelEnum

from ..routers.util_functions import create_tree, delete_all_artifacts


@pytest.mark.asyncio()
async def test_get_step_details_by_id(client: AsyncClient, engine: AsyncEngine) -> None:
    """Test `web_app.pages.step_details.get_step_details_by_id`
    function."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(client, "v1", LevelEnum.group, uuid_int)

        step, step_groups, step_scripts = await get_step_details_by_id(session, 2)
        assert len(step_scripts) == 2
        assert len(step_groups) == 5

        assert step == {
            "id": 2,
            "fullname": {"campaign": f"camp0_{uuid_int}", "step": f"step1_{uuid_int}"},
            "status": "IN_PROGRESS",
            "no_groups": 5,
            "no_groups_completed": 0,
            "no_groups_need_attention": 0,
            "no_groups_failed": 0,
            "child_config": None,
            "collections": {
                "step_input": f"cm/hsc_rc2_micro/step1_{uuid_int}/input",
                "step_output": f"cm/hsc_rc2_micro/step1_{uuid_int}_output",
                "step_public_output": f"cm/hsc_rc2_micro/step1_{uuid_int}",
                "step_validation": f"cm/hsc_rc2_micro/step1_{uuid_int}/validate",
            },
            "data": {},
            "level": LevelEnum.step.value,
            "org_status": {"name": "waiting", "value": 0},
        }

        assert step_groups == [
            {
                "id": 1,
                "name": f"group0_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": None,
                "child_config": None,
                "spec_aliases": None,
                "org_status": {"name": "waiting", "value": 0},
            },
            {
                "id": 2,
                "name": f"group1_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": None,
                "child_config": None,
                "spec_aliases": None,
                "org_status": {"name": "waiting", "value": 0},
            },
            {
                "id": 3,
                "name": f"group2_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": None,
                "child_config": None,
                "spec_aliases": None,
                "org_status": {"name": "waiting", "value": 0},
            },
            {
                "id": 4,
                "name": f"group3_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": None,
                "child_config": None,
                "spec_aliases": None,
                "org_status": {"name": "waiting", "value": 0},
            },
            {
                "id": 5,
                "name": f"group4_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "collections": None,
                "child_config": None,
                "spec_aliases": None,
                "org_status": {"name": "waiting", "value": 0},
            },
        ]

        # delete everything we just made in the session
        await delete_all_artifacts(client, "v1")

        # confirm cleanup
        campaigns = await db.Campaign.get_rows(
            session,
        )
        assert len(campaigns) == 0
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
            page.get_by_text("step_output: HSC/runs/RC2/w_2024_30/DM-45425c/step1_output"),
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

        # scripts grid
        # check first reset button is enabled and has test "Review"
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button")).to_be_enabled()
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button")).to_have_text(
            "Review"
        )
        # Reset modal dialog should be visible after clicking "Review" button
        page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button").click()
        expect(page.locator("#modalDialog")).to_be_visible()
        # Reset modal dialog should have title "Review Script"
        expect(page.locator("#reset-modal-title")).to_have_text("Review Script")
        # Target Status dropdown in Reset modal dialog
        # should have a first option "ACCEPTED"
        expect(page.locator("#targetStatus").locator("option").first).to_have_text("ACCEPTED")
        # script log path should have this text
        expect(page.locator("#scriptLogUrl")).to_contain_text(
            "/sdf/group/rubin/shared/campaigns/HSC-RC2/output/archive/"
            "HSC_DRP-RC2/w_2024_30_DM-45425c/step1/prepare_000.log",
        )
        page.get_by_role("button", name="Show Log").click()
        expect(page.locator("#errorModal")).to_be_in_viewport()
        expect(page.locator("[error-message]")).to_have_text("File not found")
        page.locator("[close-error-modal]").click()
        expect(page.locator("#errorModal")).not_to_be_visible()
        # Reset Modal should not be visible after clicking the cancel button
        page.locator("[close-reset-modal]").click()
        expect(page.locator("#modalDialog")).not_to_be_visible()
        # Script status should be changed to "ACCEPTED" and Reset button
        # should be disabled after resetting to "ACCEPTED" in the reset modal
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1)).to_contain_text("REVIEWABLE")
        page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button").click()
        expect(page.locator("#targetStatus")).to_have_value("5")
        page.locator("[confirm-reset]").click()
        expect(page.locator("#modalDialog")).not_to_be_visible()
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1)).to_contain_text("ACCEPTED")
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button")).to_be_disabled()

        # click "group0"
        page.get_by_role("link", name="group0").click()
        # check group details page is open and correct values displayed
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/group/17/171/95/")
        expect(page.get_by_text("group0", exact=True)).to_be_visible()
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/group0")).to_be_visible()

        context.close()
        browser.close()
