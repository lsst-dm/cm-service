import os

import pytest
import structlog
import uuid
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
import lsst.cmservice.common.errors as errors
from lsst.cmservice.config import config

from .util_functions import create_tree, delete_all_productions


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

        # set prereqs on steps for testing
        await db.StepDependency.create_row(
            session,
            prereq_id=check_getall[1].id,
            depend_id=check_getall[0].id,
        )

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Step.create_row(
                session,
                name="foo",
                parent_name=f"camp0{uuid_int}",
            )

        entry = check_getall[0]  # defining single unit for later

        check_getall_nonefound = await db.Step.get_rows(
            session,
            parent_name="foo",
            parent_class=db.Campaign,
        )
        assert len(check_getall_nonefound) == 0, "length should be 0"

        check_get = await db.Step.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingIDError):
            await db.Step.get_row(
                session,
                -99,
            )
        check_get_by_name = await db.Step.get_row_by_name(session, name=f"step0_{uuid_int}")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Step.get_row_by_name(session, name="foo")

        check_get_by_fullname = await db.Step.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Step.get_row_by_fullname(session, "foo")

        check_update = await db.Step.update_row(session, entry.id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar", "foo value should be bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo", "bar value should be foo"

        await db.Campaign.delete_row(session, -99)

        # run campaign specific method tests
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

        assert entry.db_id.level == LevelEnum.step, "enum should match step"

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.remove()
