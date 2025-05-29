import importlib
import os
from pathlib import Path

import pytest
import structlog
from _pytest.monkeypatch import MonkeyPatch
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice.common.enums import ScriptMethodEnum, StatusEnum

from .util_functions import cleanup


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    "script_method", [ScriptMethodEnum.bash, ScriptMethodEnum.slurm, ScriptMethodEnum.htcondor]
)
async def test_micro_db(
    engine: AsyncEngine,
    tmp_path: Path,
    script_method: ScriptMethodEnum,
    monkeypatch: MonkeyPatch,
) -> None:
    """Test fake end to end run using example/example_micro.yaml"""
    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"
    monkeypatch.setenv("FIXTURES", str(fixtures))
    ScriptHandler = importlib.import_module("lsst.cmservice.handlers.script_handler").ScriptHandler
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    monkeypatch.setattr("lsst.cmservice.config.config.butler.mock", True)

    orig_method = ScriptHandler.default_method
    ScriptHandler.default_method = script_method

    logger = structlog.get_logger(__name__)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        campaign = await interface.load_and_create_campaign(
            session=session,
            yaml_file=f"{fixtures}/test_hsc_micro.yaml",
            name="hsc_micro_w_2025_01",
            spec_block_assoc_name="hsc_micro_panda#campaign",
        )

        await campaign.update_collections(
            session,
            out="tests/micro_test",
            campaign_source="HSC/raw/RC2",
        )

        temp_dir = str(tmp_path / "archive")
        await campaign.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        changed, status = await interface.process(
            session,
            "hsc_micro_w_2025_01",
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
