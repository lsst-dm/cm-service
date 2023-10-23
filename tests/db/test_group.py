from uuid import uuid1

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db


@pytest.mark.asyncio()
async def test_group_db(engine: AsyncEngine) -> None:
    """Test `group` db table."""
    # Insert a production, a campaign, some steps, and some linked groups
    async with engine.begin() as conn:
        pname = str(uuid1())
        pid = (
            await conn.execute(insert(db.Production).returning(db.Production.id), {"name": pname})
        ).scalar_one()
        cname = str(uuid1())
        cid = (
            await conn.execute(
                insert(db.Campaign).returning(db.Campaign.id),
                {"production": pid, "name": cname},
            )
        ).scalar_one()
        snames = [str(uuid1()) for n in range(2)]
        sids = (
            (
                await conn.execute(
                    insert(db.Step).returning(db.Step.id),
                    [{"campaign": cid, "name": snames[n]} for n in range(2)],
                )
            )
            .scalars()
            .all()
        )
        gnames = [str(uuid1()) for n in range(5)]
        await conn.execute(insert(db.Group), [{"step": sids[0], "name": gnames[n]} for n in range(5)])
        await conn.execute(insert(db.Group), [{"step": sids[1], "name": gnames[n]} for n in range(5)])

    # Verify group UNIUQE name constraint
    async with engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(insert(db.Group), {"step": sids[0], "name": gnames[0]})

    # Verify group FK delete cascade
    async with engine.begin() as conn:
        await conn.execute(delete(db.Step).where(db.Step.id == sids[0]))
        assert (
            await conn.execute(select(func.count()).select_from(db.Group).where(db.Group.step == sids[0]))
        ).scalar_one() == 0
