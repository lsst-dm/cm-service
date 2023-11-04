from uuid import uuid1

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db


@pytest.mark.asyncio()
async def test_step_db(session: async_scoped_session) -> None:
    pname = str(uuid1())
    prod = await db.Production.create_row(session, name=pname)
    cnames = [str(uuid1()) for n in range(2)]
    camps = [
        await db.Campaign.create_row(session, name=cname_, spec_block_name="base#campaign", parent_name=pname)
        for cname_ in cnames
    ]
    assert len(camps) == 2

    snames = [str(uuid1()) for n in range(5)]

    steps0 = [
        await db.Step.create_row(
            session,
            name=sname_,
            spec_block_name="base#basic_step",
            parent_name=camps[0].fullname,
        )
        for sname_ in snames
    ]
    assert len(steps0) == 5

    steps1 = [
        await db.Step.create_row(
            session,
            name=sname_,
            spec_block_name="base#basic_step",
            parent_name=camps[1].fullname,
        )
        for sname_ in snames
    ]
    assert len(steps1) == 5

    with pytest.raises(IntegrityError):
        await db.Step.create_row(
            session,
            name=snames[0],
            parent_name=camps[0].fullname,
            spec_block_name="base#basic_step",
        )

    await db.Campaign.delete_row(session, camps[0].id)
    check_gone = await db.Step.get_rows(session, parent_id=camps[0].id, parent_class=db.Campaign)
    assert len(check_gone) == 0

    check_here = await db.Step.get_rows(session, parent_id=camps[1].id, parent_class=db.Campaign)
    assert len(check_here) == 8

    await db.Step.delete_row(session, steps1[0].id)

    check_here = await db.Step.get_rows(session, parent_id=camps[1].id, parent_class=db.Campaign)
    assert len(check_here) == 7

    # Finish clean up
    await db.Production.delete_row(session, prod.id)
