from sqlalchemy import select

from lsst.cmservice.db import Campaign


async def search_campaigns(session, search_term):
    print(search_term)
    q = select(Campaign)
    q.where(Campaign.fullname.contains(search_term))
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.all()
