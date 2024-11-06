import os
from pathlib import Path
from typing import Any

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine, async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface

from .util_functions import cleanup


@pytest.mark.asyncio()
async def check_script(
    session: async_scoped_session,
    parent: db.ElementMixin,
    script_name: str,
    spec_block_name: str,
    **kwargs: Any,
) -> None:
    script = await db.Script.create_row(
        session,
        parent_name=parent.fullname,
        name=script_name,
        spec_block_name=spec_block_name,
        **kwargs,
    )
    assert script.name == script_name

    changed, status = await script.process(session, fake_status=StatusEnum.reviewable)
    assert status == StatusEnum.reviewable

    await script.reject(session)

    status = await script.reset_script(session, to_status=StatusEnum.waiting, fake_reset=True)
    assert status == StatusEnum.waiting


@pytest.mark.asyncio()
async def test_handlers(
    engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Test to run the write and purge methods of various scripts"""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/example_trivial.yaml")
        assert specification.name == "trivial_htcondor"

        campaign = await interface.load_and_create_campaign(
            session,
            yaml_file="examples/example_trivial.yaml",
            name="test",
            parent_name="trivial_htcondor",
            spec_block_assoc_name="trivial_htcondor#campaign",
        )
        assert campaign.name == "test"

        collections = dict(
            out="out",
            campaign_input="campaign_input",
            campaign_source="campaign_source",
            campaign_output="campaign_output",
            inputs="inputs",
            input="input",
            output="{campaign_output}",
        )

        await check_script(session, campaign, "null", "null_script", collections=collections)

        await check_script(session, campaign, "chain_create", "chain_create_script", collections=collections)

        await check_script(
            session, campaign, "chain_prepend", "chain_prepend_script", collections=collections
        )

        await check_script(session, campaign, "tag_inputs", "tag_inputs_script", collections=collections)

        await check_script(session, campaign, "validate", "validate_script", collections=collections)

        await cleanup(session, check_cascade=True)
