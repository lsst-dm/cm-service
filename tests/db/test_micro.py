import importlib
import os
from pathlib import Path

import pytest
import structlog
from _pytest.monkeypatch import MonkeyPatch
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.common import errors
from lsst.cmservice.common.enums import ScriptMethodEnum, StatusEnum

from .util_functions import cleanup


@pytest.mark.parametrize(
    "script_method", [ScriptMethodEnum.bash, ScriptMethodEnum.slurm, ScriptMethodEnum.htcondor]
)
@pytest.mark.asyncio()
async def test_micro_db(
    engine: AsyncEngine,
    tmp_path: Path,
    script_method: ScriptMethodEnum,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test fake end to end run using example/example_micro.yaml"""
    ScriptHandler = importlib.import_module("lsst.cmservice.handlers.script_handler").ScriptHandler
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    monkeypatch.setattr("lsst.cmservice.config.config.butler.mock", True)

    orig_method = ScriptHandler.default_method
    ScriptHandler.default_method = script_method

    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        specification = await interface.load_specification(session, "examples/empty_config.yaml")
        check2 = await specification.get_block(session, "campaign")
        assert check2.name == "campaign"

        with pytest.raises(errors.CMSpecificationError):
            await specification.get_block(session, "bad")

        with pytest.raises(errors.CMSpecificationError):
            await specification.get_script_template(session, "bad")

        campaign = await interface.load_and_create_campaign(
            session,
            "examples/example_hsc_micro.yaml",
            "hsc_micro_panda",
            "w_2025_01",
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
            "hsc_micro_panda/w_2025_01",
            fake_status=StatusEnum.accepted,
        )

        assert changed
        assert status == StatusEnum.accepted

        jobs = await campaign.get_jobs(
            session,
            remaining_only=False,
        )
        assert len(jobs) == 4

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
