import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface
from lsst.cmservice.common.enums import LevelEnum, NodeTypeEnum, TableEnum, StatusEnum
import lsst.cmservice.common.errors as errors
from temp_utils import create_tree, delete_all_productions


@pytest.mark.asyncio()
async def test_handlers_interface(engine: AsyncEngine) -> None:
    """Test the interface handler"""

    uuid_int = uuid1().int
    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        await create_tree(session, LevelEnum.job, uuid_int)

        # pull something at the job level for testing
        check = await db.Job.get_rows(
            session,
            parent_name=f"prod0_{uuid_int}/camp0_{uuid_int}/step0_{uuid_int}/group0_{uuid_int}",
            parent_class=db.Group,
        )
        entry = check[0]

        check = await interface.get_row_by_table_and_id(session, entry.id, TableEnum.job)
        assert check == entry, "pulled row should match entry"

        # TODO: raises different error if bad key (e.g. TableEnum.foo)
        with pytest.raises(errors.CMBadEnumError):
            await interface.get_row_by_table_and_id(session, entry.id, 99)

        with pytest.raises(errors.CMMissingFullnameError):
            await interface.get_row_by_table_and_id(session, -99, TableEnum.job)

        check = await interface.get_node_by_level_and_id(session, entry.id, LevelEnum.job)
        assert check == entry, "pulled node should match entry"

        with pytest.raises(errors.CMBadEnumError):
            await interface.get_node_by_level_and_id(session, entry.id, 99)

        with pytest.raises(errors.CMMissingFullnameError):
            await interface.get_node_by_level_and_id(session, -99, LevelEnum.job)

        check = interface.get_node_type_by_fullname(entry.fullname)
        assert check == NodeTypeEnum.element, "should find node type is element"

        check = await interface.get_element_by_fullname(session, entry.fullname)
        assert check == entry

        with pytest.raises(errors.CMBadFullnameError):
            await interface.get_element_by_fullname(session, "foo")

        check = await interface.get_node_by_fullname(session, entry.fullname)
        assert check == entry

        # tests for coverage, unit tests elsewhere
        # mostly just making sure nothing breaks on
        # the passthrough
        check = await interface.get_spec_block(session, entry.fullname)
        assert check.name == "job"

        check = await interface.get_specification(session, entry.fullname)
        assert check.name == "base"

        check = await interface.get_resolved_collections(session, entry.fullname)
        assert len(check) == 14

        check = await interface.get_collections(session, entry.fullname)
        assert len(check) == 14

        check = await interface.get_child_config(session, entry.fullname)
        assert len(check) == 0

        check = await interface.get_data_dict(session, entry.fullname)
        assert len(check) == 9

        check = await interface.get_spec_aliases(session, entry.fullname)
        assert check["campaign"] == "campaign"

        check = await interface.update_status(session, entry.fullname, StatusEnum.reviewable)
        assert check.status == StatusEnum.reviewable

        check = await interface.update_status(session, entry.fullname, StatusEnum.waiting)
        assert check.status == StatusEnum.waiting

        check = await interface.update_child_config(session, entry.fullname)
        assert check is not None

        check = await interface.update_collections(session, entry.fullname)
        assert check is not None

        # apparently breaks other tests???
        check = await interface.update_data_dict(session, entry.fullname)
        assert check.data == {}

        check = await interface.update_spec_aliases(session, entry.fullname)
        assert check is not None

        # Finish clean up
        await delete_all_productions(session)
        await session.remove()
