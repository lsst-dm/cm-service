import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface

from .util_functions import (
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_reports_db(engine: AsyncEngine) -> None:
    """Test `job` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.job, uuid_int)

        # run row mixin method tests
        check_getall = await db.Job.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step1_{uuid_int}/group0_{uuid_int}",
            parent_class=db.Group,
        )
        assert len(check_getall) == 1, "length should be 1"

        entry = check_getall[0]  # defining single unit for later

        await interface.load_error_types(
            session,
            "examples/error_types.yaml",
        )

        await interface.load_manifest_report(
            session,
            "examples/manifest_report_2.yaml",
            entry.fullname,
        )

        # cleanup
        await cleanup(session)