import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_production_db(engine: AsyncEngine) -> None:
    """Test `production` db table."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        # Check production name UNIQUE constraint
        pname = str(uuid1())

        p1 = await db.Production.create_row(session, name=pname)
        with pytest.raises(IntegrityError):
            p1 = await db.Production.create_row(session, name=pname)

        check = await db.Production.get_row(session, p1.id)
        assert check.name == p1.name
        assert check.fullname == p1.fullname

        assert check.db_id.level == LevelEnum.production
        assert check.db_id.id == p1.id

        prods = await db.Production.get_rows(session)
        n_prod = len(prods)
        assert n_prod >= 1

        await db.Production.delete_row(session, p1.id)

        prods = await db.Production.get_rows(session)
        assert len(prods) == n_prod - 1

        # Finish clean up
        await session.remove()
