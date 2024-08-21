import os
import uuid

import pytest
import structlog
from playwright.sync_api import sync_playwright, expect
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.web_app.pages.group_details import get_group_by_id
from tests.db.util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_get_group_details_by_id(engine: AsyncEngine) -> None:
    """Test `web_app.pages.group_details.get_group_by_id` function."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.job, uuid_int)

        group, group_jobs, group_scripts = await get_group_by_id(session, 1)
        assert len(group_scripts) == 0
        assert len(group_jobs) == 1

        assert group == {
            "id": 1,
            "name": f"group0_{uuid_int}",
            "fullname": f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}/group0_{uuid_int}",
            "status": "IN_PROGRESS",
            "superseded": False,
            "child_config": {},
            "collections": {
                "group_output": f"cm/hsc_rc2_micro/step0_{uuid_int}/group0_{uuid_int}",
                "group_validation": f"cm/hsc_rc2_micro/step0_{uuid_int}/group0_{uuid_int}/validate",
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
            "step_id": 1,
            "campaign_id": 1,
        }

        assert group_jobs == [
            {
                "id": 1,
                "name": f"job_{uuid_int}",
                "superseded": False,
                "status": "IN_PROGRESS",
                "data": {},
                "submit_status": "",
                "submit_url": "",
                "stamp_url": None,
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


def test_group_details_page() -> None:
    """Test `group_details` page."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        # open group details page
        page.goto("http://0.0.0.0:8080/web_app/group/17/171/95/")
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
        expect(page.locator(".bg-teal-700").nth(1)).to_have_attribute("style", "width: 101%")
        expect(page.locator(".bg-teal-700").nth(1)).to_have_text("Running 8858")
        expect(page.locator(".bg-teal-700").nth(1).locator(".tooltip")).to_contain_text("Running")
        expect(page.locator(".bg-green-500")).to_have_attribute("style", "width: 1%")
        expect(page.locator(".bg-green-500")).to_have_text("Succeeded 1")
        expect(page.locator(".bg-green-500").locator(".tooltip")).to_contain_text("Succeeded")
        context.close()
        browser.close()
