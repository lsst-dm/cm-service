from uuid import uuid1

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db


@pytest.mark.asyncio()
async def test_campaign_db(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""
    # Insert some productions and some linked campaigns
    async with engine.begin() as conn:
        pnames = [str(uuid1()) for n in range(2)]
        pids = (
            (
                await conn.execute(
                    insert(db.Production).returning(db.Production.id),
                    [{"name": pnames[n]} for n in range(2)],
                )
            )
            .scalars()
            .all()
        )
        cnames = [str(uuid1()) for n in range(5)]
        await conn.execute(
            insert(db.Campaign),
            [{"production": pids[0], "name": cnames[n]} for n in range(5)],
        )
        await conn.execute(
            insert(db.Campaign),
            [{"production": pids[1], "name": cnames[n]} for n in range(5)],
        )

    # Verify campaign UNIQUE name constraint
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(insert(db.Campaign), {"production": pids[0], "name": cnames[0]})

    # Verify campaign FK delete cascade
    async with engine.begin() as conn:
        await conn.execute(delete(db.Production).where(db.Production.id == pids[0]))
        assert (
            await conn.execute(
                select(func.count()).select_from(db.Campaign).where(db.Campaign.production == pids[0]),
            )
        ).scalar_one() == 0
