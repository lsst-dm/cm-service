import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.exc import IntegrityError

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
import lsst.cmservice.common.errors as errors

from .util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_step_job(engine: AsyncEngine) -> None:
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
            await db.Job.create_row(
                session,
                name=f"job_{uuid_int}",
                spec_block_name="job",
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}/group0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Job.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}/group0_{uuid_int}",
            parent_class=db.Group,
        )
        assert len(check_getall) == 1, "length should be 2"

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Job.create_row(
                session,
                name="foo",
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}/group0_{uuid_int}",
            )

        entry = check_getall[0]  # defining single unit for later

        check_getall_nonefound = await db.Job.get_rows(
            session,
            parent_name="foo",
            parent_class=db.Campaign,
        )
        assert len(check_getall_nonefound) == 0, "length should be 0"

        check_get = await db.Job.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingIDError):
            await db.Job.get_row(
                session,
                -99,
            )
        check_get_by_name = await db.Job.get_row_by_name(session, name=f"job_{uuid_int}")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Job.get_row_by_name(session, name="foo")

        check_get_by_fullname = await db.Job.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        with pytest.raises(errors.CMMissingFullnameError):
            await db.Job.get_row_by_fullname(session, "foo")

        check_update = await db.Job.update_row(session, entry.id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar", "foo value should be bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo", "bar value should be foo"

        await db.Step.delete_row(session, -99)

        # run campaign specific method tests
        check = await entry.get_campaign(session)
        assert check.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.get_siblings(session)
        assert len([c for c in check]) == 0, "length of siblings should be 0"

        check = await entry.get_tasks(session)
        assert len(check.reports) == 0, "length of tasks should be 0"

        check = await entry.get_wms_reports(session)
        assert len(check.reports) == 0, "length of reports should be 0"

        check = await entry.get_products(session)
        assert len(check.reports) == 0, "length of products should be 0"

        assert entry.db_id.level == LevelEnum.job, "enum should match job"

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.remove()
