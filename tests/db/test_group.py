import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_group_db(engine: AsyncEngine) -> None:
    """Test the Group db table interface"""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check = await db.SpecBlockAssociation.get_row_by_fullname(session, "base#campaign")
        check2 = await specification.get_block(session, "campaign")
        assert check.fullname == "base#campaign"
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

        groups0 = [
            await db.Group.create_row(
                session,
                name=gname_,
                spec_block_name="group",
                parent_name=steps[0].fullname,
            )
            for gname_ in gnames
        ]
        assert len(groups0) == 5

        groups1 = [
            await db.Group.create_row(
                session,
                name=gname_,
                spec_block_name="group",
                parent_name=steps[1].fullname,
            )
            for gname_ in gnames
        ]
        assert len(groups1) == 5

        with pytest.raises(IntegrityError):
            await db.Group.create_row(
                session,
                name=gnames[0],
                parent_name=steps[0].fullname,
                spec_block_name="group",
            )

        # Finish clean up
        await db.Production.delete_row(session, prod.id)
        await session.remove()
