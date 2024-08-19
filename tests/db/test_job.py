import os

import pytest
import structlog
from safir.database import create_async_session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from lsst.cmservice import db
from lsst.cmservice.db.spec_block import SpecBlock
from lsst.cmservice.db.script_template import ScriptTemplate
from lsst.cmservice.db.handler import Handler
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.config import config
from lsst.cmservice.handlers import interface
from lsst.cmservice.common.errors import CMTooFewAcceptedJobsError

@pytest.mark.asyncio()
async def test_job(engine: AsyncEngine) -> None:
    """Test the Job object"""

    logger = structlog.get_logger(config.logger_name)
    async with engine.begin():
        session = await create_async_session(engine, logger)
        os.environ["CM_CONFIGS"] = "examples"

        specification = await interface.load_specification(session, "examples/example_standard_elements.yaml")
        _ = await interface.load_specification(session, "examples/example_standard_scripts.yaml")

        spec_block_name = "job"
        spec_block = await SpecBlock.get_row_by_fullname(session, spec_block_name)
        #spec_block = await specification.get_block(session, spec_block_name)
        handler = "lsst.cmservice.handlers.job_handler.JobHandler"

        CM_CONFIGS = "examples"
        bps_core_yaml_template = await ScriptTemplate.load(session, "bps_core_yaml_template", f"{CM_CONFIGS}/templates/example_bps_core_yaml_template.yaml")
        bps_core_script_template = await ScriptTemplate.load(session, "bps_core_script_template", f"{CM_CONFIGS}/templates/example_bps_core_script_template.yaml")
        bps_wms_script_template = await ScriptTemplate.load(session, "bps_wms_script_template", f"{CM_CONFIGS}/templates/example_bps_htcondor_script_template.yaml")

        job = db.Job("job1", "campaign/production/step/group/job1", spec_block.id, handler,
                spec_aliases={"bps_submit_script": "bps_htcondor_submit_script",
                    "bps_report_script": "bps_htcondor_report_script"},
                collections={"root": "u/ctslater/test_cm/",
                    "campaign_input": "u/ctslater/test_cm/input",
                    "campaign_ancillary": "u/ctslater/test_cm/ancillary",
                    "step_input": "u/ctslater/test_cm/campaign1",
                    },
                data={"prod_area": "./",
                      "butler_repo": "/repo/main",
                      "lsst_version": "w_2024_36",
                      "lsst_distrib_dir": "/cvmfs/sw.lsst.eu/linux-x86_64/lsst_distrib",
                      "pipeline_yaml": "${DRP_PIPE_DIR}/pipelines/HSC/DRP-RC2.yaml#isr",
                      "bps_core_yaml_template": "bps_core_yaml_template",
                      "bps_core_script_template": "bps_core_script_template",
                      "bps_wms_script_template": "bps_wms_script_template",
                      }
                )
        session.add(job)
        await session.commit()

        handler = Handler.get_handler(spec_block.id, handler)
        await handler.process(session, job)

        assert job.status == StatusEnum.running
        print(job)
        await session.refresh(job, attribute_names=["scripts_"])
        for script in job.scripts_:
            await session.refresh(script, attribute_names=["errors_"])
            print(script)
            if(script.status == StatusEnum.failed):
                print(script.errors_)


        # This runs at USDF but I get:
        # /var/spool/slurmd/job54155741/slurm_script: line 21: bps: command not found
        # in the slurm log.
        assert(job.scripts_[0].status == StatusEnum.running)

