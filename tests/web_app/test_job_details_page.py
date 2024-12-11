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
from lsst.cmservice.web_app.pages.job_details import get_job_by_id
from tests.db.util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_get_job_by_id(engine: AsyncEngine) -> None:
    """Test `web_app.pages.group_details.get_group_by_id` function."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.job, uuid_int)

        job, job_scripts = await get_job_by_id(session, 1)
        assert job_scripts is not None and len(job_scripts) == 2

        assert job == {
            "id": 1,
            "name": f"job_{uuid_int}",
            "fullname": f"prod0_{uuid_int}/camp0_{uuid_int}/step1_{uuid_int}/"
            f"group0_{uuid_int}/job_{uuid_int}_000",
            "status": "IN_PROGRESS",
            "superseded": False,
            "child_config": {},
            "collections": {
                "job_run": f"cm/hsc_rc2_micro/step1_{uuid_int}/group0_{uuid_int}/job_{uuid_int}_000",
            },
            "data": {},
            "wms_report": [],
            "aggregated_wms_report": {
                "running": 0,
                "succeeded": 0,
                "failed": 0,
                "pending": 0,
                "other": 0,
                "expected": 0,
            },
            "products": [],
        }

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
def test_job_details_page() -> None:
    """Test `job_details` page."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        # open job details page
        page.goto("http://0.0.0.0:8080/web_app/campaign/13/117/75/75/")
        # check breadcrumbs
        expect(page.get_by_role("link", name="group1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/group/13/117/75/",
        )
        expect(page.get_by_role("link", name="step1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/13/117/",
        )
        expect(page.get_by_role("link", name="w_2024_28_DM-45212d")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/13/steps/",
        )
        expect(page.get_by_role("link", name="LSSTCam-imSim_DRP-test-med-1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaigns/",
        )
        # check job name is correct
        expect(page.get_by_text("job", exact=True)).not_to_be_empty()
        # check job fullname is correct
        expect(
            page.get_by_text(
                "LSSTCam-imSim_DRP-test-med-1/w_2024_28_DM-45212d/step1/group1/job_000",
            ),
        ).not_to_be_empty()
        expect(page.get_by_text("Collections").first).not_to_be_empty()
        # check collections are correct
        expect(
            page.get_by_text("job_run: 2.2i/runs/test-med-1/w_2024_28/DM-45212d/step1/group1/job_000"),
        ).not_to_be_empty()
        # check wms task progress
        expect(page.locator(".bg-teal-700").nth(2)).to_have_attribute("style", "width: 95%")
        expect(page.locator(".bg-teal-700").nth(2)).to_have_text("Running 4940")
        expect(page.locator(".bg-teal-700").nth(2).locator(".tooltip")).to_contain_text("Running")
        expect(page.locator(".bg-green-500")).to_have_attribute("style", "width: 7%")
        expect(page.locator(".bg-green-500")).to_have_text("Succeeded 331")
        expect(page.locator(".bg-green-500").locator(".tooltip")).to_contain_text("Succeeded")

        # check wms tasks grid exists
        expect(page.locator("#wmsReportGrid")).to_be_visible()
        # check number of wms tasks (2 tasks + 1 header row)
        expect(page.locator("#wmsReportGrid").get_by_role("row")).to_have_count(3)
        expect(
            page.locator("#wmsReportGrid").get_by_role("gridcell", name="01_pipetaskInit_01"),
        ).to_have_count(1)
        expect(
            page.locator("#wmsReportGrid").get_by_role("gridcell", name="02_visit_detector_01"),
        ).to_have_count(1)
        expect(page.locator("#wmsReportGrid").get_by_role("row").nth(1)).to_contain_text("1")
        expect(page.locator("#wmsReportGrid").get_by_role("row").nth(2)).to_contain_text("4940")
        expect(page.locator("#wmsReportGrid").get_by_role("row").nth(2)).to_contain_text("330")

        # check scripts grid exists
        expect(page.locator("#scriptsGrid")).to_be_visible()
        # check number of step scripts (4 scripts + 1 header row)
        expect(page.locator("#scriptsGrid").get_by_role("row")).to_have_count(5)
        # click on "manifest_report" script
        expect(page.get_by_role("link", name="manifest_report", exact=True)).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/script/13/117/75/75/540/",
        )
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(3)).to_contain_text("WAITING")
        # check first reset button is disabled
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(1).get_by_role("button")).to_be_disabled()
        # check third reset button is enabled and has test "Reset"
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(2).get_by_role("button")).to_be_enabled()
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(2).get_by_role("button")).to_have_text(
            "Reset"
        )
        # Reset modal dialog should be visible after clicking "Reset" button
        page.locator("#scriptsGrid").get_by_role("row").nth(2).get_by_role("button").click()
        expect(page.locator("#modalDialog")).to_be_visible()
        # Reset modal dialog should have title "Reset Script"
        expect(page.locator("#reset-modal-title")).to_have_text("Reset Script")
        # Target Status dropdown in Reset modal dialog
        # should have a first option "WAITING"
        expect(page.locator("#targetStatus").locator("option").first).to_have_text("WAITING")
        # Reset Modal should not be visible after clicking the cancel button
        page.locator("[close-reset-modal]").click()
        expect(page.locator("#modalDialog")).not_to_be_visible()
        # Script status should be changed to "WAITING" and Reset button
        # should be disabled after resetting to "WAITING" in the reset modal
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(2)).to_contain_text("FAILED")
        page.locator("#scriptsGrid").get_by_role("row").nth(2).get_by_role("button").click()
        expect(page.locator("#targetStatus")).to_have_value("0")
        page.locator("[confirm-reset]").click()
        expect(page.locator("#modalDialog")).not_to_be_visible()
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(3)).to_contain_text("WAITING")
        expect(page.locator("#scriptsGrid").get_by_role("row").nth(2).get_by_role("button")).to_be_disabled()

        # check products grid exists
        expect(page.locator("#productsGrid")).to_be_visible()
        # check number of step products (only 1 header row)
        expect(page.locator("#productsGrid").get_by_role("row")).to_have_count(1)
        context.close()
        browser.close()
