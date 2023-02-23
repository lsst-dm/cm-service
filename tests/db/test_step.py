from uuid import uuid1

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db


@pytest.mark.asyncio
async def test_step_db(engine: AsyncEngine) -> None:
    """Test `step` db table"""

    # Insert a production, some campaigns, and some linked steps
    async with engine.begin() as conn:
        pname = str(uuid1())
        pid = (
            await conn.execute(insert(db.Production).returning(db.Production.id), {"name": pname})
        ).scalar_one()
        cnames = [str(uuid1()) for n in range(2)]
        cids = (
            (
                await conn.execute(
                    insert(db.Campaign).returning(db.Campaign.id),
                    [{"production": pid, "name": cnames[n]} for n in range(2)],
                )
            )
            .scalars()
            .all()
        )
        snames = [str(uuid1()) for n in range(5)]
        await conn.execute(insert(db.Step), [{"campaign": cids[0], "name": snames[n]} for n in range(5)])
        await conn.execute(insert(db.Step), [{"campaign": cids[1], "name": snames[n]} for n in range(5)])

    # Verify step UNIQUE name sconstraint
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(insert(db.Step), {"campaign": cids[0], "name": snames[0]})

    # Verify step FK delete cascade
    async with engine.begin() as conn:
        await conn.execute(delete(db.Campaign).where(db.Campaign.id == cids[0]))
        assert (
            await conn.execute(select(func.count()).select_from(db.Step).where(db.Step.campaign == cids[0]))
        ).scalar_one() == 0
