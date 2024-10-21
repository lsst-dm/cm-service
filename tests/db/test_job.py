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
from lsst.cmservice.handlers import interface

from .util_functions import (
    check_get_methods,
    check_queue,
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

        await check_get_methods(session, entry, db.Job, db.Group)

        with pytest.raises(errors.CMMissingIDError):
            await db.Job.delete_row(session, -99)

        # run job specific method tests
        campaign = await entry.get_campaign(session)
        assert campaign.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.get_siblings(session)
        assert len([c for c in check]) == 0, "length of siblings should be 0"

        check = await entry.get_errors(session)
        assert len(check) == 0, "length of errors should be 0"

        check = await interface.get_task_sets_for_job(session, entry.fullname)
        assert len(check) == 0, "length of task sets should be 0"

        check = await interface.get_wms_reports_for_job(session, entry.fullname)
        assert len(check) == 0, "length of wms reports should be 0"

        check = await interface.get_product_sets_for_job(session, entry.fullname)
        assert len(check) == 0, "length of products should be 0"

        check = await interface.get_errors_for_job(session, entry.fullname)
        assert len(check) == 0, "length of errors should be 0"

        sleep_time = await campaign.estimate_sleep_time(session)
        assert sleep_time == 10, "Wrong sleep time"

        # check update methods
        await check_update_methods(session, entry, db.Job)

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
