from uuid import uuid1

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db


@pytest.mark.asyncio()
async def test_group_db(session: async_scoped_session) -> None:
    pname = str(uuid1())
    prod = await db.Production.create_row(session, name=pname)
    cname = str(uuid1())
    camp = await db.Campaign.create_row(
        session,
        name=cname,
        spec_block_assoc_name="base#campaign",
        parent_name=pname,
    )
    snames = [str(uuid1()) for n in range(2)]

    steps = [
        await db.Step.create_row(
            session,
            name=sname_,
            spec_block_assoc_name="base#basic_step",
            parent_name=camp.fullname,
        )
        for sname_ in snames
    ]

    gnames = [str(uuid1()) for n in range(5)]

    groups0 = [
        await db.Group.create_row(
            session,
            name=gname_,
            spec_block_assoc_name="base#group",
            parent_name=steps[0].fullname,
        )
        for gname_ in gnames
    ]
    assert len(groups0) == 5

    groups1 = [
        await db.Group.create_row(
            session,
            name=gname_,
            spec_block_assoc_name="base#group",
            parent_name=steps[1].fullname,
        )
        for gname_ in gnames
    ]
    assert len(groups1) == 5

    with pytest.raises(IntegrityError):
        await db.Group.create_row(
            session,
            name=gnames[0],
            parent_name=steps[0].fullname,
            spec_block_assoc_name="base#group",
        )

    # Finish clean up
    await db.Production.delete_row(session, prod.id)
