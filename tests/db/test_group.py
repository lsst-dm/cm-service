import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.common.enums import LevelEnum
import lsst.cmservice.common.errors as errors

from .util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_group_db(engine: AsyncEngine) -> None:
    """Test `step` db table."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
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
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Group.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}",
            parent_class=db.Step,
        )
        assert len(check_getall) == 5, "length should be 5"

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Group.create_row(
                session,
                name="foo",
                parent_name=f"step0_{uuid_int}",
            )

        entry = check_getall[0]  # defining single unit for later

        check_getall_nonefound = await db.Group.get_rows(
            session,
            parent_name="foo",
            parent_class=db.Step,
        )
        assert len(check_getall_nonefound) == 0, "length should be 0"

        check_get = await db.Group.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingIDError):
            await db.Group.get_row(
                session,
                -99,
            )
        check_get_by_name = await db.Group.get_row_by_name(session, name=f"group0_{uuid_int}")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Group.get_row_by_name(session, name="foo")

        check_get_by_fullname = await db.Group.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Group.get_row_by_fullname(session, "foo")

        check_update = await db.Group.update_row(session, entry.id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar", "foo value should be bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo", "bar value should be foo"

        await db.Group.delete_row(session, -99)

        # run campaign specific method tests
        check = await entry.get_campaign(session)
        assert check.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.children(session)
        assert len([c for c in check]) == 1, "length of children should be 1"

        check = await entry.get_tasks(session)
        assert len(check.reports) == 0, "length of tasks should be 0"

        check = await entry.get_wms_reports(session)
        assert len(check.reports) == 0, "length of reports should be 0"

        check = await entry.get_products(session)
        assert len(check.reports) == 0, "length of products should be 0"

        assert entry.db_id.level == LevelEnum.group, "enum should match group"

        # test bad state error in rescue_job
        with pytest.raises(errors.CMBadStateTransitionError):
            await entry.rescue_job(session)

        # test null error in mark_job_rescued
        with pytest.raises(errors.CMBadStateTransitionError):
            await entry.mark_job_rescued(session)

        # test key error in get_create_kwargs
        with pytest.raises(KeyError):
            await db.Group.get_create_kwargs(session, parent_name="foo", name="bar")

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.remove()
