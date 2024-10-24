import os

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
@pytest.mark.skip("Not yet baby")
async def test_daemon(engine: AsyncEngine) -> None:
    """Test creating a job, add it to the work queue, and start processing."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        CM_CONFIGS = "examples"
        os.environ["CM_CONFIGS"] = CM_CONFIGS

        campaign = await interface.load_and_create_campaign(
            session,
            "examples/example_trivial.yaml",
            "trivial_panda",
            "test_daemon",
            "trivial_panda#campaign",
        )

        await campaign.update_collections(
            session,
            out="tests/daemon_test",
            campaign_source="HSC/raw/RC2",
        )

        changed, status = await interface.process(
            session,
            "trivial_panda/test_daemon",
        )

        """

        # Add the job to the work queue, to be processed by the daemon.
        queue_entry = db.Queue.create(job, time_created=datetime.now(),
           time_updated=datetime.now())
        session.add(queue_entry)
        await session.commit()

        await daemon_iteration(session)

        # Confirm that scripts were created and that one started running.
        await session.refresh(job, attribute_names=["scripts_"])
        assert len(job.scripts_) > 0
        assert job.scripts_[0].status == StatusEnum.running

        # Confirm that the work queue knows to wait before re-checking.
        await session.refresh(queue_entry)
        assert queue_entry.time_next_check > datetime.now()

        time.sleep(20)

        # Manually run the daemon to process any available work.
        await daemon_iteration(session)

        await session.refresh(job, attribute_names=["scripts_"])
        assert job.scripts_[0].status == StatusEnum.failed

        for script in job.scripts_:
            await session.refresh(script, attribute_names=["errors_"])
            print(script)
            if script.status == StatusEnum.failed:
                print(script.errors_)

        """
