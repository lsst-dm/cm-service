import os
from pathlib import Path

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

import lsst.cmservice.common.errors as errors
from lsst.cmservice import db
from lsst.cmservice.common.enums import ScriptMethodEnum, StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface
from lsst.cmservice.handlers.script_handler import ScriptHandler


@pytest.mark.parametrize(
    "script_method", [ScriptMethodEnum.bash, ScriptMethodEnum.slurm, ScriptMethodEnum.htcondor]
)
@pytest.mark.asyncio()
async def test_micro(
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

        # temp_dir = str(tmp_path / "archive")
        temp_dir = f"output_test/{script_method.name}/archive"
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

        # now we clean up
        await db.Production.delete_row(session, 1)

        this_spec = await db.Specification.get_row_by_fullname(session, "hsc_micro_panda")
        await db.Specification.delete_row(session, this_spec.id)

        # make sure we cleaned up
        n_campaigns = len(await db.Campaign.get_rows(session))
        n_steps = len(await db.Step.get_rows(session))
        n_groups = len(await db.Group.get_rows(session))
        n_jobs = len(await db.Job.get_rows(session))
        n_scripts = len(await db.Script.get_rows(session))
        n_step_dependencies = len(await db.StepDependency.get_rows(session))
        n_script_dependencies = len(await db.ScriptDependency.get_rows(session))

        assert n_campaigns == 0
        assert n_steps == 0
        assert n_groups == 0
        assert n_jobs == 0
        assert n_scripts == 0

        assert n_step_dependencies == 0
        assert n_script_dependencies == 0

        await session.remove()

    ScriptHandler.default_method = orig_method
