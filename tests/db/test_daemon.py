import os
from asyncio import sleep
from datetime import UTC, datetime
from pathlib import Path

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.daemon import daemon_iteration
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.handlers import interface

from .util_functions import cleanup


@pytest.mark.asyncio()
async def test_daemon_db(engine: AsyncEngine) -> None:
    """Test creating a job, add it to the work queue, and start processing."""

    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"
    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        CM_CONFIGS = "examples"
        os.environ["CM_CONFIGS"] = CM_CONFIGS

        campaign = await interface.load_and_create_campaign(
            session=session,
            yaml_file=f"{fixtures}/test_trivial.yaml",
            name="test_daemon",
            spec_block_assoc_name="trivial_panda#campaign",
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
            time_created=datetime.now(tz=UTC),
            time_updated=datetime.now(tz=UTC),
            active=True,
        )

        await daemon_iteration(session)
        await session.refresh(campaign)

        assert campaign.status.value >= StatusEnum.running.value

        await sleep(2)
        await queue_entry.update_values(
            session,
            time_next_check=datetime.now(tz=UTC),
        )
        await session.commit()

        await daemon_iteration(session)
        await sleep(2)
        await session.refresh(campaign)

        assert campaign.status is StatusEnum.accepted

        await db.Queue.get_rows(
            session,
        )

        await cleanup(session, check_cascade=True)
