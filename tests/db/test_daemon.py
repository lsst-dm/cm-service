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

from .util_functions import delete_all_productions, delete_all_spec_stuff


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

        queues = await db.Queue.get_rows(
            session,
        )
        for queue_ in queues:
            await db.Queue.delete_row(session, queue_.id)

        queues = await db.Queue.get_rows(
            session,
        )
        assert len(queues) == 0

        await delete_all_productions(session)
        await delete_all_spec_stuff(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0

        # make sure we cleaned up
        n_campaigns = len(await db.Campaign.get_rows(session))
        n_steps = len(await db.Step.get_rows(session))
        n_groups = len(await db.Group.get_rows(session))
        n_jobs = len(await db.Job.get_rows(session))
        n_scripts = len(await db.Script.get_rows(session))
        n_step_dependencies = len(await db.StepDependency.get_rows(session))
        n_script_dependencies = len(await db.ScriptDependency.get_rows(session))

        n_specs = len(await db.Specification.get_rows(session))
        n_spec_blocks = len(await db.SpecBlock.get_rows(session))
        n_script_templates = len(await db.ScriptTemplate.get_rows(session))

        assert n_campaigns == 0
        assert n_steps == 0
        assert n_groups == 0
        assert n_jobs == 0
        assert n_scripts == 0

        assert n_step_dependencies == 0
        assert n_script_dependencies == 0

        assert n_specs == 0
        assert n_spec_blocks == 0
        assert n_script_templates == 0

        await session.commit()
        await session.remove()
