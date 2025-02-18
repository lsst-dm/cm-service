import importlib
import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common import errors
from lsst.cmservice.common.enums import LevelEnum, StatusEnum

from .util_functions import (
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_job_db(engine: AsyncEngine) -> None:
    """Test `job` db table."""
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(__name__)
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

        parent = await entry.get_parent(session)

        await db.Job.update_row(session, entry.id, status=StatusEnum.running)
        sleep_time = await parent.estimate_sleep_time(session)
        assert sleep_time == 300
        await db.Job.update_row(session, entry.id, status=StatusEnum.waiting)

        await check_get_methods(session, entry, db.Job, db.Group)

        with pytest.raises(errors.CMMissingIDError):
            await db.Job.delete_row(session, -99)

        # run job specific method tests
        campaign = await entry.get_campaign(session)
        assert campaign.name == f"camp0_{uuid_int}", "should return same name as camp0"

        check = await entry.get_siblings(session)
        assert len(list(check)) == 0, "length of siblings should be 0"

        check = await entry.get_errors(session)  # type: ignore
        assert len(check) == 0, "length of errors should be 0"

        sleep_time = await campaign.estimate_sleep_time(session)
        assert sleep_time == 10, "Wrong sleep time"

        # check update methods
        await check_update_methods(session, entry, db.Job)

        # check scripts
        await check_scripts(session, entry)

        # check on the rescue job
        with pytest.raises(errors.CMTooFewAcceptedJobsError):
            await parent.rescue_job(session)  # type: ignore

        await db.Job.update_row(session, entry.id, status=StatusEnum.rescuable)
        job2 = await parent.rescue_job(session)  # type: ignore

        with pytest.raises(errors.CMBadStateTransitionError):
            await parent.mark_job_rescued(session)  # type: ignore

        await db.Job.update_row(session, entry.id, status=StatusEnum.rescuable)
        with pytest.raises(errors.CMBadStateTransitionError):
            await parent.mark_job_rescued(session)  # type: ignore

        await db.Job.update_row(session, entry.id, status=StatusEnum.rescuable)
        await db.Job.update_row(session, job2.id, status=StatusEnum.accepted)

        rescued = await parent.mark_job_rescued(session)  # type: ignore
        assert len(rescued) == 1, "Wrong number of rescued jobs"

        await db.Job.update_row(session, entry.id, status=StatusEnum.accepted)
        await db.Job.update_row(session, job2.id, status=StatusEnum.accepted)
        with pytest.raises(errors.CMTooManyActiveScriptsError):
            await parent.mark_job_rescued(session)  # type: ignore

        await db.Job.update_row(session, entry.id, status=StatusEnum.rescuable)
        await db.Job.update_row(session, job2.id, status=StatusEnum.rescuable)

        job3 = await parent.rescue_job(session)  # type: ignore

        await db.Job.update_row(session, entry.id, status=StatusEnum.rescued)
        await db.Job.update_row(session, job2.id, status=StatusEnum.failed, superseded=True)
        await db.Job.update_row(session, job3.id, status=StatusEnum.rescuable)

        with pytest.raises(errors.CMTooFewAcceptedJobsError):
            await parent.mark_job_rescued(session)  # type: ignore

        job4 = await parent.rescue_job(session)  # type: ignore
        await db.Job.update_row(session, job4.id, status=StatusEnum.accepted)

        rescued = await interface.mark_job_rescued(session, parent.fullname)
        assert len(rescued) == 1, "Wrong number of rescued jobs"

        # make and test queue object
        await check_queue(session, entry)

        # cleanup
        await cleanup(session)
