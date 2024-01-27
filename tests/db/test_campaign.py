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
async def test_campaign_db(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check = await db.SpecBlockAssociation.get_row_by_fullname(session, "base#campaign")
        check2 = await specification.get_block(session, "campaign")
        assert check.fullname == "base#campaign"
        assert check2.name == "campaign"

        pnames = [str(uuid1()) for n in range(2)]
        prods = [await db.Production.create_row(session, name=pname_) for pname_ in pnames]
        cnames = [str(uuid1()) for n in range(5)]

        camps0 = [
            await db.Campaign.create_row(
                session,
                name=cname_,
                spec_block_assoc_name="base#campaign",
                parent_name=pnames[0],
            )
            for cname_ in cnames
        ]
        assert len(camps0) == 5

        camps1 = [
            await db.Campaign.create_row(
                session,
                name=cname_,
                spec_block_assoc_name="base#campaign",
                parent_name=pnames[1],
            )
            for cname_ in cnames
        ]
        assert len(camps1) == 5

        with pytest.raises(IntegrityError):
            await db.Campaign.create_row(
                session,
                name=cnames[0],
                parent_name=pnames[0],
                spec_block_assoc_name="base#campaign",
            )

        await db.Production.delete_row(session, prods[0].id)

        check_gone = await db.Campaign.get_rows(session, parent_id=prods[0].id, parent_class=db.Production)
        assert len(check_gone) == 0

        check_here = await db.Campaign.get_rows(session, parent_id=prods[1].id, parent_class=db.Production)
        assert len(check_here) == 5

        await db.Campaign.delete_row(session, camps1[0].id)

        check_here = await db.Campaign.get_rows(session, parent_id=prods[1].id, parent_class=db.Production)
        assert len(check_here) == 4

        # Finish clean up
        await db.Production.delete_row(session, prods[1].id)
        await session.remove()
