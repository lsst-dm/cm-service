import os

import pytest
import structlog
import uuid
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
import lsst.cmservice.common.errors as errors
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config

from .util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_campaign_db(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.step, uuid_int)

        with pytest.raises(IntegrityError):
            await db.Campaign.create_row(
                session,
                name=f"camp0_{uuid_int}",
                spec_block_assoc_name="base#campaign",
                parent_name=f"prod0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Campaign.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}",
            parent_class=db.Production,
        )
        assert len(check_getall) == 1, "length should be 1"

        entry = check_getall[0]  # defining single unit for later

        check_getall_nonefound = await db.Campaign.get_rows(
            session,
            parent_name="prod0_bad",
            parent_class=db.Production,
        )
        assert len(check_getall_nonefound) == 0, "length should be 0"

        check_get = await db.Campaign.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingIDError):
            await db.Campaign.get_row(
                session,
                -99,
            )

        check_get_by_name = await db.Campaign.get_row_by_name(session, name=f"camp0_{uuid_int}")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Campaign.get_row_by_name(session, name="foo")

        check_get_by_fullname = await db.Campaign.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Campaign.get_row_by_fullname(session, "foo")

        check_update = await db.Campaign.update_row(session, entry.id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar", "foo value should be bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo", "bar value should be foo"

        await db.Campaign.delete_row(session, -99)

        # run campaign specific method tests
        check = await entry.children(session)
        assert len([c for c in check]) == 2, "length of children should be 2"

        check = await entry.get_tasks(session)
        assert len(check.reports) == 0, "length of tasks should be 0"

        check = await entry.get_wms_reports(session)
        assert len(check.reports) == 0, "length of reports should be 0"

        check = await entry.get_products(session)
        assert len(check.reports) == 0, "length of products should be 0"

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.remove()
