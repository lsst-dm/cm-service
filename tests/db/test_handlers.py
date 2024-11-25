import os
from pathlib import Path
from typing import Any

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine, async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface, jobs

from .util_functions import cleanup, create_tree


@pytest.mark.asyncio()
async def check_run_script(
    session: async_scoped_session,
    parent: db.ElementMixin,
    script_name: str,
    spec_block_name: str,
    **kwargs: Any,
) -> db.Script:
    script = await db.Script.create_row(
        session,
        parent_name=parent.fullname,
        name=script_name,
        spec_block_name=spec_block_name,
        **kwargs,
    )
    assert script.name == script_name

    _changed, status = await interface.process(
        session,
        f"script:{script.fullname}",
        fake_status=StatusEnum.reviewable,
    )
    # FIXME: What do we expect in terms of return type here?
    assert status.value >= StatusEnum.running.value

    return script


@pytest.mark.asyncio()
async def check_script(
    session: async_scoped_session,
    parent: db.ElementMixin,
    script_name: str,
    spec_block_name: str,
    **kwargs: Any,
) -> db.Script:
    script = await db.Script.create_row(
        session,
        parent_name=parent.fullname,
        name=script_name,
        spec_block_name=spec_block_name,
        **kwargs,
    )
    assert script.name == script_name

    _changed, status = await interface.process(
        session,
        f"script:{script.fullname}",
        fake_status=StatusEnum.ready,
    )
    assert status == StatusEnum.ready

    _changed, status = await script.process(session, fake_status=StatusEnum.reviewable)
    if status != StatusEnum.reviewable:
        errors = await script.get_script_errors(session)
        raise ValueError(f"{str(errors)}")

    await script.reject(session)

    status = await script.reset_script(session, to_status=StatusEnum.prepared, fake_reset=True)
    assert status == StatusEnum.prepared

    status = await script.reset_script(session, to_status=StatusEnum.ready, fake_reset=True)
    assert status == StatusEnum.ready

    status = await script.reset_script(session, to_status=StatusEnum.waiting, fake_reset=True)
    assert status == StatusEnum.waiting

    return script


@pytest.mark.asyncio()
async def test_handlers_campaign_level_db(
    engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Test to run the write and purge methods of various scripts"""
    temp_dir = str(tmp_path / "archive")

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        await create_tree(session, LevelEnum.campaign, 0)

        campaign = (await db.Campaign.get_rows(session))[0]

        await campaign.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        collections: dict[str, str | list[str]] = dict(
            out="out",
            campaign_input="campaign_input",
            campaign_source="campaign_source",
            campaign_output="campaign_output",
            campaign_resource_usage="campaign_resource_usage",
            campaign_hips_maps="campaign_hips_maps",
            inputs="inputs",
            input="input",
            output="{campaign_output}",
        )

        data = dict(
            lsst_distrib_dir="lsst_distrib_dir",
            resource_usage_script_template="stack_script_template",
            hips_maps_script_template="stack_script_template",
            hips_pipeline_yaml_path="/stack_files/highres_hips_rc2.yaml",
            hips_pipeline_config_path="/stack_files/gen_hips_both_rc2.yaml",
        )

        await check_run_script(session, campaign, "run", "run_steps", collections=collections)

        await check_script(session, campaign, "null", "null_script", collections=collections)

        await check_script(session, campaign, "chain_create", "chain_create_script", collections=collections)

        collections2 = collections.copy()
        collections2["inputs"] = ["input1", "input2"]
        await check_script(
            session, campaign, "chain_create2", "chain_create_script", collections=collections2
        )

        await check_script(
            session, campaign, "chain_prepend", "chain_prepend_script", collections=collections
        )

        await check_script(
            session, campaign, "chain_collect_steps", "chain_collect_steps_script", collections=collections
        )

        await check_script(session, campaign, "tag_inputs", "tag_inputs_script", collections=collections)

        await check_script(session, campaign, "tag_create", "tag_create_script", collections=collections)

        await check_script(
            session, campaign, "tag_associate", "tag_associate_script", collections=collections
        )

        await check_script(session, campaign, "validate", "validate_script", collections=collections)

        await check_script(
            session, campaign, "resource_usage", "resource_usage_script", collections=collections, data=data
        )

        await check_script(
            session, campaign, "hips_maps", "hips_maps_script", collections=collections, data=data
        )

        await cleanup(session, check_cascade=True)


@pytest.mark.asyncio()
async def test_handlers_step_level_db(
    engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Test to run the write and purge methods of various scripts"""
    temp_dir = str(tmp_path / "archive")

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        await create_tree(session, LevelEnum.step, 0)

        step = (await db.Step.get_rows(session))[0]

        await step.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        collections = dict(
            out="out",
            campaign_input="campaign_input",
            campaign_source="campaign_source",
            campaign_output="campaign_output",
            inputs="inputs",
            input="input",
            output="{campaign_output}",
        )

        await check_run_script(session, step, "run", "run_groups", collections=collections)

        await check_script(session, step, "prepare_step", "prepare_step_script", collections=collections)

        await cleanup(session, check_cascade=True)


@pytest.mark.asyncio()
async def test_handlers_group_level_db(
    engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Test to run the write and purge methods of various scripts"""
    temp_dir = str(tmp_path / "archive")

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        await create_tree(session, LevelEnum.group, 0)

        group = (await db.Group.get_rows(session))[0]

        await group.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        collections = dict(
            out="out",
            run="run",
            campaign_input="campaign_input",
            campaign_source="campaign_source",
            campaign_output="campaign_output",
            inputs="inputs",
            input="input",
            output="{campaign_output}",
        )

        dict(
            lsst_distrib_dir="lsst_distrib_dir",
            bps_core_yaml_template="bps_core_yaml_template",
            bps_core_script_template="bps_core_script_template",
            bps_panda_script_template="bps_panda_script_template",
            bps_htcondor_script_template="bps_htcondor_script_template",
            manifest_script_template="stack_script_template",
        )

        run_jobs = await check_run_script(session, group, "run", "run_jobs", collections=collections)

        await db.Script.update_row(session, run_jobs.id, status=StatusEnum.reviewable)

        _changed, status = await run_jobs.process(session, fake_status=StatusEnum.reviewable)
        assert status.value >= StatusEnum.reviewable.value

        status = await run_jobs.review(session, fake_status=StatusEnum.accepted)
        assert status == StatusEnum.accepted

        await db.Group.update_row(session, group.id, status=StatusEnum.reviewable)
        _changed, status = await group.process(session)
        assert status == StatusEnum.accepted

        await cleanup(session, check_cascade=True)


@pytest.mark.asyncio()
async def test_handlers_job_level_db(
    engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """Test to run the write and purge methods of various scripts"""
    temp_dir = str(tmp_path / "archive")

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"
        await create_tree(session, LevelEnum.job, 0)

        job = (await db.Job.get_rows(session))[0]

        await job.update_data_dict(
            session,
            prod_area=temp_dir,
        )

        collections = dict(
            out="out",
            run="run",
            campaign_input="campaign_input",
            campaign_source="campaign_source",
            campaign_output="campaign_output",
            inputs="inputs",
            input="input",
            output="{campaign_output}",
        )

        data = dict(
            lsst_distrib_dir="lsst_distrib_dir",
            bps_core_yaml_template="bps_core_yaml_template",
            bps_core_script_template="bps_core_script_template",
            bps_panda_script_template="bps_panda_script_template",
            bps_htcondor_script_template="bps_htcondor_script_template",
            manifest_script_template="stack_script_template",
        )

        await check_script(
            session, job, "bps_panda_submit", "bps_panda_submit_script", collections=collections, data=data
        )

        bps_panda_report = await check_script(
            session, job, "bps_panda_report", "bps_panda_report_script", collections=collections, data=data
        )

        await db.WmsTaskReport.create_row(
            session,
            job_id=job.id,
            name="dummy_report",
            fullname=f"{job.fullname}#dummy_report",
        )

        await db.Script.update_row(
            session,
            bps_panda_report.id,
            status=StatusEnum.prepared,
        )
        status = await bps_panda_report.reset_script(session, to_status=StatusEnum.waiting, fake_reset=True)
        assert status == StatusEnum.waiting

        await check_script(
            session,
            job,
            "bps_htcondor_submit",
            "bps_htcondor_submit_script",
            collections=collections,
            data=data,
        )

        await check_script(
            session,
            job,
            "bps_htcondor_report",
            "bps_htcondor_report_script",
            collections=collections,
            data=data,
        )

        await check_script(
            session, job, "manifest_report", "manifest_report_script", collections=collections, data=data
        )

        manifest_report_load = await check_script(
            session, job, "manifest_report_load", "manifest_report_load", collections=collections, data=data
        )

        await interface.load_manifest_report(
            session,
            "examples/manifest_report_review_error.yaml",
            fullname=job.fullname,
        )

        await db.Script.update_row(
            session,
            manifest_report_load.id,
            status=StatusEnum.prepared,
        )
        status = await manifest_report_load.reset_script(
            session, to_status=StatusEnum.waiting, fake_reset=True
        )
        assert status == StatusEnum.waiting

        assert jobs.PandaScriptHandler.get_job_id({"Run Id": 322}) == 322
        assert jobs.HTCondorScriptHandler.get_job_id({"Submit dir": "dummy"}) == "dummy"

        await cleanup(session, check_cascade=True)
