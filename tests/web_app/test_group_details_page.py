import os
import uuid

import pytest
import structlog
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
