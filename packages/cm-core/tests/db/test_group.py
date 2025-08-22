import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.core import db
from lsst.cmservice.core.common import errors
from lsst.cmservice.core.common.enums import LevelEnum

from .util_functions import (
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_group_db(engine: AsyncEngine) -> None:
    """Test `group` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.job, uuid_int)

        with pytest.raises(IntegrityError):
            await db.Group.create_row(
                session,
                name=f"group0_{uuid_int}",
                spec_block_name="group",
                parent_name=f"camp0_{uuid_int}/step1_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Group.get_rows(
            session,
            parent_name=f"camp0_{uuid_int}/step1_{uuid_int}",
            parent_class=db.Step,
        )
        assert len(check_getall) == 5, "length should be 5"

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Group.create_row(
                session,
                name="foo",
                parent_name=f"step1_{uuid_int}",
            )

        entry = check_getall[0]  # defining single unit for later

        await check_get_methods(session, entry, db.Group, db.Step)

        with pytest.raises(errors.CMMissingIDError):
            await db.Group.delete_row(session, -99)

        # run group specific method tests
        campaign = await entry.get_campaign(session)
        assert campaign.name == f"camp0_{uuid_int}", "should return same name as camp0"

        children = await entry.children(session)
        assert len(list(children)) == 1, "length of children should be 1"

        # check update methods
        await check_update_methods(session, entry, db.Group)

        # check scripts
        await check_scripts(session, entry)

        # test bad state error in rescue_job
        with pytest.raises(errors.CMTooFewAcceptedJobsError):
            await entry.rescue_job(session)

        # test null error in mark_job_rescued
        with pytest.raises(errors.CMBadStateTransitionError):
            await entry.mark_job_rescued(session)

        # test key error in get_create_kwargs
        with pytest.raises(KeyError):
            await db.Group.get_create_kwargs(session, parent_name="foo", name="bar")

        # make and test queue object
        await check_queue(session, entry)

        # cleanup
        await cleanup(session)
