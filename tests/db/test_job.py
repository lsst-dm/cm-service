import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_job_db(engine: AsyncEngine) -> None:
    """Test the Job db table interface"""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        pname = str(uuid1())
        prod = await db.Production.create_row(session, name=pname)
        cname = str(uuid1())
        camp = await db.Campaign.create_row(
            session,
            name=cname,
            spec_block_assoc_name="base#campaign",
            parent_name=pname,
        )
        snames = [str(uuid1()) for n in range(2)]

        steps = [
            await db.Step.create_row(
                session,
                name=sname_,
                spec_block_name="basic_step",
                parent_name=camp.fullname,
            )
            for sname_ in snames
        ]

        gnames = [str(uuid1()) for n in range(5)]

        groups = [
            await db.Group.create_row(
                session,
                name=gname_,
                spec_block_name="group",
                parent_name=steps[0].fullname,
            )
            for gname_ in gnames
        ]
        assert len(groups) == 5

        jobs = [
            await db.Job.create_row(
                session,
                name="job",
                spec_block_name="job",
                parent_name=group_.fullname,
            )
            for group_ in groups
        ]
        assert len(jobs) == 5

        # test we can retrieve properties entered
        entry = jobs[0]
        check = await db.Job.get_row(session, entry.id)
        assert check.db_id.id == entry.db_id.id

        # test that we can retrieve the campaign
        check = await entry.get_campaign(session)
        assert check.db_id.id == camp.db_id.id

        # test null result on fetching downstream
        check = await entry.get_tasks(session)
        assert check is not None

        check = await entry.get_wms_reports(session)
        assert check is not None

        check = await entry.get_products(session)
        assert check is not None

        # test key error in get_create_kwargs
        with pytest.raises(KeyError):
            await db.Job.get_create_kwargs(session, parent_name="foo", name="bar")

        # Finish clean up
        await db.Production.delete_row(session, prod.id)
        await session.remove()
