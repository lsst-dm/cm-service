"""Tests v2 database operations"""

from uuid import uuid5

import pytest
from sqlmodel import select

from lsst.cmservice.db.campaigns_v2 import Campaign, _default_campaign_namespace
from lsst.cmservice.db.session import DatabaseSessionDependency


@pytest.mark.asyncio
async def test_create_campaigns_v2(testdb: DatabaseSessionDependency) -> None:
    assert testdb.sessionmaker is not None

    campaign_name = "test_campaign"
    campaign = Campaign(
        id=uuid5(_default_campaign_namespace, campaign_name),
        name=campaign_name,
        namespace=_default_campaign_namespace,
        owner="test",
        metadata_={"mtime": 0, "crtime": 0},
        configuration={"mtime": 0, "crtime": 0},
    )
    async with testdb.sessionmaker() as session:
        session.add(campaign)
        await session.commit()

    del campaign

    async with testdb.sessionmaker() as session:
        statement = select(Campaign).where(Campaign.name == "test_campaign")
        results = await session.exec(statement)
        campaign = results.one()
        campaign.name = "a_new_name"
        campaign.configuration["mtime"] = 1750107719
        campaign.metadata_["crtime"] = 1750107719
        await session.commit()

    del campaign

    async with testdb.sessionmaker() as session:
        statement = select(Campaign).where(Campaign.name == "a_new_name")
        results = await session.exec(statement)
        campaign = results.one()
        assert campaign.name == "a_new_name"
        assert "mtime" in campaign.configuration
        assert "crtime" in campaign.metadata_
        assert campaign.configuration["mtime"] == 1750107719
        assert campaign.configuration["crtime"] == 0
        assert campaign.metadata_["crtime"] == 1750107719
        assert campaign.metadata_["mtime"] == 0
