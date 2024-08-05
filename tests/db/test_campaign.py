import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.errors import CMMissingRowCreateInputError, CMSpecficiationError
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface

from util_functions import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def bob_campaign_db(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")

        with pytest.raises(CMSpecficiationError):
            await specification.get_block(session, "does_not_exist")
        with pytest.raises(CMSpecficiationError):
            await specification.get_script_template(session, "does_not_exist")

        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        pnames = [str(uuid1()) for n in range(2)]
        prods = [await db.Production.create_row(session, name=pname_) for pname_ in pnames]
        cnames = [str(uuid1()) for n in range(5)]

        camps0 = [
            await db.Campaign.create_row(
                session,
                name=cname_,
                spec_block_assoc_name="base#campaign",
                parent_name=pnames[0],
            )
            for cname_ in cnames
        ]
        assert len(camps0) == 5

        camps1 = [
            await db.Campaign.create_row(
                session,
                name=cname_,
                spec_name="base",
                parent_name=pnames[1],
            )
            for cname_ in cnames
        ]
        assert len(camps1) == 5

        with pytest.raises(IntegrityError):
            await db.Campaign.create_row(
                session,
                name=cnames[0],
                parent_name=pnames[0],
                spec_block_assoc_name="base#campaign",
            )

        with pytest.raises(CMMissingRowCreateInputError):
            await db.Campaign.create_row(
                session,
                name=cnames[0],
                parent_name=pnames[0],
            )

        with pytest.raises(ValueError):
            await db.Campaign.create_row(
                session,
                name=cnames[0],
                parent_name=pnames[0],
                spec_block_assoc_name="base#campaign#bad",
            )

        await db.Production.delete_row(session, prods[0].id)

        check_gone = await db.Campaign.get_rows(session, parent_id=prods[0].id, parent_class=db.Production)
        assert len(check_gone) == 0

        check_here = await db.Campaign.get_rows(session, parent_id=prods[1].id, parent_class=db.Production)
        assert len(check_here) == 5

        await db.Campaign.delete_row(session, camps1[0].id)

        check_here = await db.Campaign.get_rows(session, parent_id=prods[1].id, parent_class=db.Production)
        assert len(check_here) == 4

        check_get = await db.Campaign.get_row(session, check_here[0].id)
        assert check_get.id == check_here[0].id

        check_get_by_fullname = await db.Campaign.get_row_by_fullname(session, check_here[0].fullname)
        assert check_get_by_fullname.id == check_here[0].id

        check_update = await db.Campaign.update_row(session, check_here[0].id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo"

        entry = check_here[0]

        # test null result on fetching downstream
        check = await entry.children(session)
        assert check is not None

        check = await entry.get_tasks(session)
        assert check is not None

        check = await entry.get_wms_reports(session)
        assert check is not None

        check = await entry.get_products(session)
        assert check is not None

        # Finish clean up
        await db.Production.delete_row(session, prods[1].id)
        await session.remove()


@pytest.mark.asyncio()
async def test_campaign_db_v2(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.step)

        # run row mixin method tests
        check_getall = await db.Campaign.get_rows(session, parent_name="prod0", parent_class=db.Production)
        assert len(check_getall) == 1, "length should be 1"

        entry = check_getall[0]

        check_get = await db.Campaign.get_row(session, entry.id)
        assert check_get.id == entry.id, "pulled row should be identical"

        check_get_by_name = await db.Campaign.get_row_by_name(session, name="camp0")
        assert check_get_by_name.id == entry.id, "pulled row should be identical"

        check_get_by_fullname = await db.Campaign.get_row_by_fullname(session, entry.fullname)
        assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

        check_update = await db.Campaign.update_row(session, entry.id, data=dict(foo="bar"))
        assert check_update.data["foo"] == "bar", "foo value should be bar"

        check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
        assert check_update2.data["bar"] == "foo", "bar value should be foo"

        # run campaign specific method tests
        # TODO: make proper asserts on this.
        check = await entry.children(session)
        assert check is not None

        check = await entry.get_tasks(session)
        assert check is not None

        check = await entry.get_wms_reports(session)
        assert check is not None

        check = await entry.get_products(session)
        assert check is not None

        # delete everything we just made in the session
        await delete_all_productions(session)

        # confirm cleanup
        productions = await db.Production.get_rows(
            session,
        )
        assert len(productions) == 0
        await session.remove()
