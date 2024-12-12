import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common import errors
from lsst.cmservice.common.enums import LevelEnum

from .util_functions import (
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_step_db(engine: AsyncEngine) -> None:
    """Test `step` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(__name__)
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

        with pytest.raises(errors.CMMissingIDError):
            await db.Step.delete_row(session, -99)

        # run step specific method tests
        check1 = await entry.get_campaign(session)
        assert check1.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check2 = await entry.get_all_prereqs(session)
        assert len(check2) == 1, "should be one prereq"

        check3 = await entry.children(session)
        assert len(list(check3)) == 5, "length of children should be 5"

        # check update methods
        await check_update_methods(session, entry, db.Step)

        # check scripts
        await check_scripts(session, entry)

        # make and test queue object
        await check_queue(session, entry)

        # cleanup
        await cleanup(session)
