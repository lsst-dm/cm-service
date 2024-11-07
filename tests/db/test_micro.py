import os
from pathlib import Path

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

import lsst.cmservice.common.errors as errors
from lsst.cmservice.common.enums import ScriptMethodEnum, StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface
from lsst.cmservice.handlers.script_handler import ScriptHandler

from .util_functions import cleanup


@pytest.mark.parametrize(
    "script_method", [ScriptMethodEnum.bash, ScriptMethodEnum.slurm, ScriptMethodEnum.htcondor]
)
@pytest.mark.asyncio()
async def test_micro_db(
    engine: AsyncEngine,
    tmp_path: Path,
    script_method: ScriptMethodEnum,
) -> None:
    """Test fake end to end run using example/example_micro.yaml"""

    orig_method = ScriptHandler.default_method
    ScriptHandler.default_method = script_method

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        with pytest.raises(errors.CMSpecficiationError):
            await specification.get_block(session, "bad")

        with pytest.raises(errors.CMSpecficiationError):
            await specification.get_script_template(session, "bad")

        script_template = await specification.get_script_template(session, "bps_core_script_template")
        assert script_template.name == "bps_core_script_template", "Script template name mismatch"

        await script_template.update_from_file(
            session,
            script_template.name,
            "examples/templates/example_bps_core_script_template.yaml",
        )

        campaign = await interface.load_and_create_campaign(
            session,
            "examples/example_hsc_micro.yaml",
            "hsc_micro_panda",
            "w_2023_41",
            "hsc_micro_panda#campaign",
        )

        await campaign.update_collections(
            session,
            out="tests/micro_test",
            campaign_source="HSC/raw/RC2",
        )

        temp_dir = str(tmp_path / "archive")
        # use this line if you want to be able to inspect the outputs
        # temp_dir = f"output_test/{script_method.name}/archive"
        await campaign.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        changed, status = await interface.process(
            session,
            "hsc_micro_panda/w_2023_41",
            fake_status=StatusEnum.accepted,
        )

        assert changed
        assert status == StatusEnum.accepted

        jobs = await campaign.get_jobs(
            session,
            remaining_only=False,
        )
        assert len(jobs) == 6

        changed, status = await campaign.run_check(
            session,
            do_checks=True,
            force_check=True,
            fake_status=StatusEnum.accepted,
        )
        assert status == StatusEnum.accepted

        status = await campaign.review(
            session,
            fake_status=StatusEnum.accepted,
        )
        assert status == StatusEnum.accepted

        await cleanup(session, check_cascade=True)

    ScriptHandler.default_method = orig_method
