import os
import uuid

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common import errors
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface

from .util_functions import (
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
)


@pytest.mark.asyncio()
async def test_campaign_db(engine: AsyncEngine) -> None:
    """Test `campaign` db table."""

    db.handler.Handler.reset_cache()

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        # intialize a tree down to one level lower
        await create_tree(session, LevelEnum.step, uuid_int)

        # test the upsert mechanism
        await interface.load_specification(session, "examples/empty_config.yaml", allow_update=True)

        with pytest.raises(IntegrityError):
            await db.Campaign.create_row(
                session,
                name=f"camp0_{uuid_int}",
                spec_block_assoc_name="base#campaign",
                parent_name=f"prod0_{uuid_int}",
            )

        # explict tests of get_create_kwargs parsing
        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Campaign.get_create_kwargs(
                session,
                parent_name=f"prod0_{uuid_int}",
                name=f"camp0_{uuid_int}",
            )

        await db.Campaign.get_create_kwargs(
            session,
            parent_name=f"prod0_{uuid_int}",
            name=f"camp0_{uuid_int}",
            spec_name="base",
        )

        with pytest.raises(ValueError):
            await db.Campaign.get_create_kwargs(
                session,
                parent_name=f"prod0_{uuid_int}",
                name=f"camp0_{uuid_int}",
                spec_block_assoc_name="bad",
            )

        await db.Campaign.get_create_kwargs(
            session,
            parent_name=f"prod0_{uuid_int}",
            name=f"camp0_{uuid_int}",
            spec_block_assoc_name="base#campaign",
            data=None,
            child_config=None,
            collections=None,
            spec_aliases=None,
        )

        # run row mixin method tests
        check_getall = await db.Campaign.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}",
            parent_class=db.Production,
        )
        assert len(check_getall) == 1, "length should be 1"

        check_getall = await db.Campaign.get_rows(
            session,
            parent_class=db.Production,
            parent_id=-99,
        )
        assert len(check_getall) == 0, "length should be 0"

        check_getall = await db.Campaign.get_rows(
            session,
            parent_class=db.Production,
            parent_id=1,
        )
        assert len(check_getall) == 1, "length should be 1"

        check_getall = await db.Campaign.get_rows(
            session,
            parent_class=db.Production,
        )
        assert len(check_getall) == 1, "length should be 1"

        entry = check_getall[0]  # defining single unit for later

        with pytest.raises(errors.CMMissingRowCreateInputError):
            await db.Script.create_row(session)

        handler = db.handler.Handler.get_handler(
            entry.spec_block_id,
            "lsst.cmservice.handlers.element_handler.CampaignHandler",
        )
        assert not handler.data
        assert handler.get_handler_class_name()

        await check_get_methods(session, entry, db.Campaign, db.Production)

        with pytest.raises(errors.CMMissingIDError):
            await db.Campaign.delete_row(session, -99)

        with pytest.raises(errors.CMBadFullnameError):
            await interface.get_element_by_fullname(session, "")

        with pytest.raises(errors.CMBadFullnameError):
            await interface.get_element_by_fullname(session, "//////")

        # run campaign specific method tests
        check = await entry.children(session)
        assert len(list(check)) == 2, "length of children should be 2"

        # check update methods
        await check_update_methods(session, entry, db.Campaign)

        # check scripts
        await check_scripts(session, entry)

        # make and test queue object
        await check_queue(session, entry)

        # cleanup
        await cleanup(session)
