import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

import lsst.cmservice.common.errors as errors
from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_scripts,
    check_update_methods,
    create_tree,
    delete_all_productions,
)


@pytest.mark.asyncio()
async def test_job_db(engine: AsyncEngine) -> None:
    """Test `job` db table."""

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
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step1_{uuid_int}/group0_{uuid_int}",
            )

        # run row mixin method tests
        check_getall = await db.Job.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step1_{uuid_int}/group0_{uuid_int}",
            parent_class=db.Group,
        )
        assert len(check_getall) == 1, "length should be 1"

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Job.create_row(
                session,
                name="foo",
                parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step1_{uuid_int}/group0_{uuid_int}",
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

        await db.Job.delete_row(session, -99)

        # run job specific method tests
        campaign = await entry.get_campaign(session)
        assert campaign.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.get_siblings(session)
        assert len([c for c in check]) == 0, "length of siblings should be 0"

        check = await entry.get_tasks(session)
        assert len(check.reports) == 0, "length of tasks should be 0"

        check = await entry.get_wms_reports(session)
        assert len(check.reports) == 0, "length of reports should be 0"

        check = await entry.get_products(session)
        assert len(check.reports) == 0, "length of products should be 0"

        check = await entry.get_errors(session)
        assert len(check) == 0, "length of errors should be 0"

        sleep_time = await campaign.estimate_sleep_time(session)
        assert sleep_time == 10, "Wrong sleep time"

        assert entry.db_id.level == LevelEnum.job, "enum should match job"

        # check update methods
        await check_update_methods(session, entry)

        # check scripts
        await check_scripts(session, entry)

        # check on the rescue job
        parent = await entry.get_parent(session)

        with pytest.raises(errors.CMTooFewAcceptedJobsError):
            new_job = await parent.rescue_job(session)

        await entry.update_values(session, status=StatusEnum.rescuable)
        new_job = await parent.rescue_job(session)

        with pytest.raises(errors.CMBadStateTransitionError):
            await parent.mark_job_rescued(session)

        await entry.update_values(session, status=StatusEnum.rescuable)
        with pytest.raises(errors.CMBadStateTransitionError):
            await parent.mark_job_rescued(session)

        await entry.update_values(session, status=StatusEnum.rescuable)
        await new_job.update_values(session, status=StatusEnum.accepted)

        rescued = await parent.mark_job_rescued(session)
        assert len(rescued) == 1, "Wrong number of rescued jobs"

        await entry.update_values(session, status=StatusEnum.accepted)
        with pytest.raises(errors.CMTooManyActiveScriptsError):
            await parent.mark_job_rescued(session)

        await entry.update_values(session, status=StatusEnum.rescuable)
        await new_job.update_values(session, status=StatusEnum.rescuable)

        with pytest.raises(errors.CMTooFewAcceptedJobsError):
            await parent.mark_job_rescued(session)

        await entry.update_values(session, status=StatusEnum.rescuable)
        await new_job.update_values(session, status=StatusEnum.rescuable)

        newest_job = await parent.rescue_job(session)
        await newest_job.update_values(session, status=StatusEnum.accepted)

        rescued = await parent.mark_job_rescued(session)
        assert len(rescued) == 2, "Wrong number of rescued jobs"

        # make and test queue object
        queue = await db.Queue.create_row(session, fullname=entry.fullname)

        assert queue.element_db_id.level == entry.level
        check_elem = await queue.get_element(session)
        assert check_elem.id == entry.id

        check_queue = await db.Queue.get_queue_item(session, fullname=entry.fullname)
        assert check_queue.element_id == entry.id

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.commit()
        await session.remove()
