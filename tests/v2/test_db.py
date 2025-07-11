"""Tests v2 database operations"""

from uuid import uuid4, uuid5

import pytest
from sqlmodel import select

from lsst.cmservice.db.campaigns_v2 import Campaign, Machine, _default_campaign_namespace
from lsst.cmservice.db.session import DatabaseManager


@pytest.mark.asyncio
async def test_create_campaigns_v2(testdb: DatabaseManager) -> None:
    """Tests the campaigns_v2 table by creating and updating a Campaign."""

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


@pytest.mark.asyncio
async def test_create_machines_v2(testdb: DatabaseManager) -> None:
    """Tests the machines_v2 table by storing + retrieving a pickled object."""

    assert testdb.sessionmaker is not None

    # the machines table is a PickleType so it doesn't really matter for this
    # test what kind of object is being pickled.
    o = {"a": [1, 2, 3, 4, {"aa": [[0, 1], [2, 3]]}]}

    machine_id = uuid4()
    machine = Machine(id=machine_id, state=o)
    async with testdb.sessionmaker() as session:
        session.add(machine)
        await session.commit()

    async with testdb.sessionmaker() as session:
        s = select(Machine).where(Machine.id == machine_id).limit(1)
        unpickled = (await session.exec(s)).one()

    assert unpickled.state == o
