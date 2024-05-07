from sqlalchemy import select

from lsst.cmservice.db import Step


async def get_campaign_steps(session, campaign_id):
    q = select(Step).where(Step.parent_id == campaign_id)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()
