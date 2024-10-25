import os
from datetime import datetime

import pause
import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.daemon import daemon_iteration
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface

from .util_functions import cleanup


@pytest.mark.asyncio()
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

        # Add the job to the work queue, to be processed by the daemon.
        queue_entry = await db.Queue.create_row(
            session,
            fullname=campaign.fullname,
            time_created=datetime.now(),
            time_updated=datetime.now(),
        )

        await daemon_iteration(session)
        await session.refresh(campaign)

        assert campaign.status.value >= StatusEnum.running.value

        pause.sleep(2)
        await queue_entry.update_values(
            session,
            time_next_check=datetime.now(),
        )
        await session.commit()

        await daemon_iteration(session)
        await session.refresh(campaign)

        assert campaign.status == StatusEnum.accepted

        await db.Queue.get_rows(
            session,
        )

        await cleanup(session, check_cascade=True)
