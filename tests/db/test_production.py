from uuid import uuid1

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db


@pytest.mark.asyncio()
async def test_production_db(engine: AsyncEngine) -> None:
    """Test `production` db table."""
    # Check production name UNIQUE constraint
    pname = str(uuid1())
    async with engine.begin() as conn:
        await conn.execute(insert(db.Production).returning(db.Production.id), {"name": pname})
        with pytest.raises(IntegrityError):
            await conn.execute(insert(db.Production).returning(db.Production.id), {"name": pname})
