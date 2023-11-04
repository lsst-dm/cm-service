from uuid import uuid1

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum


@pytest.mark.asyncio()
async def test_production_db(session: async_scoped_session) -> None:
    """Test `production` db table."""

    # Check production name UNIQUE constraint
    pname = str(uuid1())

    p1 = await db.Production.create_row(session, name=pname)
    with pytest.raises(IntegrityError):
        p1 = await db.Production.create_row(session, name=pname)

    check = await db.Production.get_row(session, p1.id)
    assert check.name == p1.name
    assert check.fullname == p1.fullname

    assert check.db_id.level == LevelEnum.production
    assert check.db_id.id == p1.id

    prods = await db.Production.get_rows(session)
    n_prod = len(prods)
    assert n_prod >= 1

    await db.Production.delete_row(session, p1.id)

    prods = await db.Production.get_rows(session)
    assert len(prods) == n_prod - 1
