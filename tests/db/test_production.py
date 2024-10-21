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

from .util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_production_db(engine: AsyncEngine) -> None:
    """Test `production` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.campaign, uuid_int)

        with pytest.raises(IntegrityError):
            await db.Production.create_row(
                session,
                name=f"prod0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Production.get_rows(
            session,
        )
        assert len(check_getall) == 1, "length should be 1"

        entry = check_getall[0]  # defining single unit for later

        check_get = await db.Production.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingIDError):
            await db.Production.get_row(
                session,
                -99,
            )

        check_get_by_name = await db.Production.get_row_by_name(session, name=f"prod0_{uuid_int}")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Production.get_row_by_name(session, name="foo")

        check_get_by_fullname = await db.Production.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Production.get_row_by_fullname(session, "foo")

        check_update = await db.Production.update_row(session, entry.id, name="foo")
        assert check_update.name == "foo", "name should be foo"

        check_update2 = await check_update.update_values(session, name="bar")
        assert check_update2.name == "bar", "name should be bar"

        assert entry.level == LevelEnum.production, "level should match production"

        with pytest.raises(errors.CMMissingIDError):
            await db.Production.delete_row(session, -99)

        # run campaign specific method tests
        check = await entry.children(session)
        assert len([c for c in check]) == 1, "length of children should be 2"

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.commit()
        await session.remove()
