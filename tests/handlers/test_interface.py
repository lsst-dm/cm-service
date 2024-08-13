import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface
from lsst.cmservice.common.enums import LevelEnum, NodeTypeEnum, TableEnum
import lsst.cmservice.common.errors as errors


@pytest.mark.asyncio()
async def test_step_db(engine: AsyncEngine) -> None:
    """Test the Step db table interface"""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        pname = str(uuid1())
        prod = await db.Production.create_row(session, name=pname)
        cnames = [str(uuid1()) for n in range(2)]
        camps = [
            await db.Campaign.create_row(
                session,
                name=cname_,
                spec_block_assoc_name="base#campaign",
                parent_name=pname,
            )
            for cname_ in cnames
        ]
        assert len(camps) == 2

        snames = [str(uuid1()) for n in range(5)]

        steps0 = [
            await db.Step.create_row(
                session,
                name=sname_,
                spec_block_name="basic_step",
                parent_name=camps[0].fullname,
            )
            for sname_ in snames
        ]
        assert len(steps0) == 5

        entry = steps0[0]

        check = await interface.get_row_by_table_and_id(session, entry.id, TableEnum.step)
        assert check == entry, "pulled row should match entry"

        # TODO: raises different error if bad key (e.g. TableEnum.foo)
        with pytest.raises(errors.CMBadEnumError):
            await interface.get_row_by_table_and_id(session, entry.id, 99)

        with pytest.raises(errors.CMMissingFullnameError):
            await interface.get_row_by_table_and_id(session, -99, TableEnum.step)

        check = await interface.get_node_by_level_and_id(session, entry.id, LevelEnum.step)
        assert check == entry, "pulled node should match entry"

        with pytest.raises(errors.CMBadEnumError):
            await interface.get_node_by_level_and_id(session, entry.id, 99)

        with pytest.raises(errors.CMMissingFullnameError):
            await interface.get_node_by_level_and_id(session, -99, LevelEnum.step)

        check = interface.get_node_type_by_fullname(entry.fullname)
        assert check == NodeTypeEnum.element, "should find node type is element"

        check = await interface.get_element_by_fullname(session, entry.fullname)
        assert check == entry

        # Finish clean up
        await db.Production.delete_row(session, prod.id)
        await session.remove()
