import os
import uuid

import pytest
import structlog
from playwright.sync_api import expect, sync_playwright
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.web_app.pages.group_details import get_group_by_id
from tests.db.util_functions import create_tree, delete_all_artifacts


@pytest.mark.asyncio()
async def test_get_group_details_by_id(engine: AsyncEngine) -> None:
    """Test `web_app.pages.group_details.get_group_by_id` function."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.job, uuid_int)

        group, group_jobs, group_scripts = await get_group_by_id(session, 1)
        assert group_scripts is not None and len(group_scripts) == 2
        assert group_jobs is not None and len(group_jobs) == 1

        assert group == {
            "id": 1,
            "name": f"group0_{uuid_int}",
            "fullname": f"camp0_{uuid_int}/step1_{uuid_int}/group0_{uuid_int}",
            "status": "IN_PROGRESS",
            "superseded": False,
            "child_config": {},
            "collections": {
                "group_output": f"cm/hsc_rc2_micro/step1_{uuid_int}/group0_{uuid_int}",
                "group_validation": f"cm/hsc_rc2_micro/step1_{uuid_int}/group0_{uuid_int}/validate",
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
            "step_id": 2,
            "campaign_id": 1,
            "level": LevelEnum.group.value,
            "org_status": {"name": "waiting", "value": 0},
        }

        assert group_jobs == [
            {
                "id": 1,
                "name": f"job_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS - WAITING",
                "data": {},
                "submit_status": "",
                "submit_url": "",
                "stamp_url": None,
            },
        ]

        # delete everything we just made in the session
        await delete_all_artifacts(session)

        await session.close()
        await session.remove()


@pytest.mark.playwright
def test_group_details_page() -> None:
    """Test `group_details` page."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        # open group details page
        page.goto("http://0.0.0.0:8080/web_app/group/17/171/95/")
        # check breadcrumbs
        expect(page.get_by_role("link", name="step1")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/17/171/",
        )
        expect(page.get_by_role("link", name="w_2024_30_DM-45425c")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaign/17/steps/",
        )
        expect(page.get_by_role("link", name="HSC_DRP-RC2")).to_have_attribute(
            "href",
            "http://0.0.0.0:8080/web_app/campaigns/",
        )
        # check group name is correct
        expect(page.get_by_text("group0", exact=True)).not_to_be_empty()
        # check group fullname is correct
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/group0")).not_to_be_empty()
        # check collections section
        expect(page.get_by_text("Collections").first).not_to_be_empty()
        # check collections are correct
        expect(
            page.get_by_text("group_output: HSC/runs/RC2/w_2024_30/DM-45425c/step1/group0"),
        ).not_to_be_empty()
        expect(
            page.get_by_text("group_validation: HSC/runs/RC2/w_2024_30/DM-45425c/step1/group0/validate"),
        ).not_to_be_empty()
        # check data values are correct
        expect(
            page.get_by_text(
                "data_query: instrument='HSC' and skymap='hsc_rings_v1' "
                "AND (318 <= exposure) and (exposure < 1308)",
            ),
        ).not_to_be_empty()
        # check wms task progress
        expect(page.locator(".bg-teal-700").nth(2)).to_have_attribute("style", "width: 101%")
        expect(page.locator(".bg-teal-700").nth(2)).to_have_text("Running 8858")
        expect(page.locator(".bg-teal-700").nth(2).locator(".tooltip")).to_contain_text("Running")
        expect(page.locator(".bg-green-500")).to_have_attribute("style", "width: 1%")
        expect(page.locator(".bg-green-500")).to_have_text("Succeeded 1")
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
        expect(page.locator("#wmsReportGrid")).to_contain_text("8858")
        # check scripts grid exists
        expect(page.locator("#scriptsGrid")).to_be_visible()
        # check number of step scripts (1 script + 1 header row)
        expect(page.locator("#scriptsGrid").get_by_role("row")).to_have_count(2)
        # click on "run" script
        page.get_by_role("link", name="run").click()
        # check that script details page is open and has the correct values
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/script/17/171/95/722/")
        expect(page.get_by_text("run", exact=True)).to_be_visible()
        expect(
            page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/group0/run_000"),
        ).to_be_visible()
        # back to group details page
        page.get_by_role("link", name="group0").click()
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/group/17/171/95/")
        # check jobs grid exists
        expect(page.locator("#jobsGrid")).to_be_visible()
        # check number of group jobs (1 job + 1 header row)
        expect(page.locator("#jobsGrid").get_by_role("row")).to_have_count(2)
        # click "job"
        page.get_by_role("link", name="job").click()
        # check job details page is open and correct values displayed
        expect(page).to_have_url("http://0.0.0.0:8080/web_app/campaign/17/171/95/95/")
        expect(page.get_by_text("job", exact=True)).to_be_visible()
        expect(page.get_by_text("HSC_DRP-RC2/w_2024_30_DM-45425c/step1/group0/job_000")).to_be_visible()

        context.close()
        browser.close()
