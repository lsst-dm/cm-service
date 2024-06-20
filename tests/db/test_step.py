import os
from uuid import uuid1

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.common.errors import CMMissingRowCreateInputError
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface


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

        with pytest.raises(CMMissingRowCreateInputError):
            await db.Step.create_row(
                session,
                name="bad",
                parent_name=camps[0].fullname,
            )

        steps1 = [
            await db.Step.create_row(
                session,
                name=sname_,
                spec_block_name="basic_step",
                parent_name=camps[1].fullname,
            )
            for sname_ in snames
        ]
        assert len(steps1) == 5

        for i in range(4):
            await db.StepDependency.create_row(
                session,
                prereq_id=steps1[i].id,
                depend_id=steps1[i + 1].id,
            )

        prereqs = await steps1[4].get_all_prereqs(session)
        assert len(prereqs) == 4
        assert prereqs[0].id == steps1[3].id

        await session.refresh(steps1[4], attribute_names=["prereqs_"])
        assert steps1[4].prereqs_[0].prereq_db_id.id == steps1[3].id
        assert steps1[4].prereqs_[0].depend_db_id.id == steps1[4].id
        assert not await steps1[4].prereqs_[0].is_done(session)

        entry = steps1[4]

        # test that we can retrieve the campaign
        check_camp = await entry.get_campaign(session)
        assert check_camp.db_id.id == camps[1].db_id.id

        # test null result on fetching downstream
        check = await check_camp.children(session)
        assert check is not None

        check = await check_camp.get_tasks(session)
        assert check is not None

        check = await check_camp.get_wms_reports(session)
        assert check is not None

        check = await check_camp.get_products(session)
        assert check is not None

        # test null result on fetching downstream
        assert entry.db_id.level == LevelEnum.step
        assert entry.db_id.id == entry.id

        check = await entry.children(session)
        assert check is not None

        check = await entry.get_tasks(session)
        assert check is not None

        check = await entry.get_wms_reports(session)
        assert check is not None

        check = await entry.get_products(session)
        assert check is not None

        with pytest.raises(IntegrityError):
            await db.Step.create_row(
                session,
                name=snames[0],
                parent_name=camps[0].fullname,
                spec_block_name="basic_step",
            )

        await db.Campaign.delete_row(session, camps[0].id)
        check_gone = await db.Step.get_rows(session, parent_id=camps[0].id, parent_class=db.Campaign)
        assert len(check_gone) == 0

        check_here = await db.Step.get_rows(session, parent_id=camps[1].id, parent_class=db.Campaign)
        assert len(check_here) == 5

        await db.Step.delete_row(session, steps1[0].id)

        check_here = await db.Step.get_rows(session, parent_id=camps[1].id, parent_class=db.Campaign)
        assert len(check_here) == 4

        # Finish clean up
        await db.Production.delete_row(session, prod.id)
        await session.remove()
