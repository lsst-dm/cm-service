import os
import time
from datetime import datetime

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.common.daemon import daemon_iteration
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.db.script_template import ScriptTemplate
from lsst.cmservice.db.spec_block import SpecBlock
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_daemon(engine: AsyncEngine) -> None:
    """Test creating a job, add it to the work queue, and start processing."""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        CM_CONFIGS = "examples"
        os.environ["CM_CONFIGS"] = CM_CONFIGS

        await interface.load_yaml(session, "examples/example_standard_elements.yaml")
        await interface.load_yaml(session, "examples/example_standard_scripts.yaml")

        await ScriptTemplate.load(
            session,
            "bps_core_yaml_template",
            f"{CM_CONFIGS}/templates/example_bps_core_yaml_template.yaml",
        )
        await ScriptTemplate.load(
            session,
            "bps_core_script_template",
            f"{CM_CONFIGS}/templates/example_bps_core_script_template.yaml",
        )
        await ScriptTemplate.load(
            session,
            "bps_wms_script_template",
            f"{CM_CONFIGS}/templates/example_bps_htcondor_script_template.yaml",
        )

        spec_block_name = "job"
        spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
        handler_name = "lsst.cmservice.handlers.job_handler.JobHandler"

        job = db.Job(
            name="job1",
            fullname="campaign/production/step/group/job1",
            spec_block_id=spec_block.id,
            handler=handler_name,
            spec_aliases={
                "bps_submit_script": "bps_htcondor_submit_script",
                "bps_report_script": "bps_htcondor_report_script",
            },
            collections={
                "root": "u/ctslater/test_cm/",
                "campaign_input": "u/ctslater/test_cm/input",
                "campaign_ancillary": "u/ctslater/test_cm/ancillary",
                "step_input": "u/ctslater/test_cm/campaign1",
                "out": "u/ctslater/test_cm/isolated_job_output",
            },
            data={
                "prod_area": "./",
                "data_query": "instrument = 'HSC' and visit=318 and detector=20",
                "butler_repo": "/repo/main",
                "lsst_version": "w_2024_37",
                "lsst_distrib_dir": "/cvmfs/sw.lsst.eu/linux-x86_64/lsst_distrib",
                "pipeline_yaml": "${DRP_PIPE_DIR}/pipelines/HSC/DRP-RC2.yaml#isr",
                "bps_core_yaml_template": "bps_core_yaml_template",
                "bps_core_script_template": "bps_core_script_template",
                "bps_wms_script_template": "bps_wms_script_template",
            },
        )
        session.add(job)
        await session.commit()

        # Add the job to the work queue, to be processed by the daemon.
        queue_entry = db.Queue(job, time_created=datetime.now(), time_updated=datetime.now())
        session.add(queue_entry)
        await session.commit()

        await daemon_iteration(session)

        # Confirm that scripts were created and that one started running.
        await session.refresh(job, attribute_names=["scripts_"])
        assert len(job.scripts_) > 0
        assert job.scripts_[0].status == StatusEnum.running

        # Confirm that the work queue knows to wait before re-checking.
        await session.refresh(queue_entry)
        assert queue_entry.time_next_check > datetime.now()

        time.sleep(20)

        # Manually run the daemon to process any available work.
        await daemon_iteration(session)

        await session.refresh(job, attribute_names=["scripts_"])
        assert job.scripts_[0].status == StatusEnum.failed

        for script in job.scripts_:
            await session.refresh(script, attribute_names=["errors_"])
            print(script)
            if script.status == StatusEnum.failed:
                print(script.errors_)
