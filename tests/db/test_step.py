import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

import lsst.cmservice.common.errors as errors
from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    create_tree,
    delete_all_productions,
)


@pytest.mark.asyncio()
async def test_step_db(engine: AsyncEngine) -> None:
    """Test `step` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.group, uuid_int)

        with pytest.raises(IntegrityError):
            await db.Step.create_row(
                session,
                name=f"step0_{uuid_int}",
                spec_block_name="basic_step",
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Step.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}",
            parent_class=db.Campaign,
        )
        assert len(check_getall) == 2, "length should be 2"

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Step.create_row(
                session,
                name="foo",
                parent_name=f"camp0{uuid_int}",
            )

        entry = check_getall[1]  # defining single unit for later

        await check_get_methods(session, entry, db.Step, db.Campaign)

        await db.Step.delete_row(session, -99)

        # run step specific method tests
        check = await entry.get_campaign(session)
        assert check.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.get_all_prereqs(session)
        assert len(check) == 1, "should be one prereq"

        check = await entry.children(session)
        assert len([c for c in check]) == 5, "length of children should be 5"

        check = await entry.get_tasks(session)
        assert len(check.reports) == 0, "length of tasks should be 0"

        check = await entry.get_wms_reports(session)
        assert len(check.reports) == 0, "length of reports should be 0"

        check = await entry.get_products(session)
        assert len(check.reports) == 0, "length of products should be 0"

        sleep_time = await entry.estimate_sleep_time(session)
        assert sleep_time == 10, "Wrong sleep time"

        assert entry.db_id.level == LevelEnum.step, "enum should match step"

        # check update methods
        await check_update_methods(session, entry, db.Step)

        # check scripts
        await check_scripts(session, entry)

        # make and test queue object
        await check_queue(session, entry)

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.commit()
        await session.remove()
