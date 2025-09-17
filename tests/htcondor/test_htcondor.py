import sys

import pytest
from anyio import Path

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="htcondor package only available on linux")


async def test_job_event_log() -> None:
    """Tests the parsing of an htcondor job event log."""
    from lsst.cmservice.common.htcondor import HTCondorManager

    good_log = Path(__file__).parent.parent / "fixtures/logs" / "job_good.condorlog"
    mgr = HTCondorManager()
    result = await mgr.check(cluster_id=19634626, condor_log=good_log)
    assert result


async def test_sub_file_parsing() -> None:
    """Tests the generation of an htcondor submit description dictionary from
    a sub file.
    """
    from lsst.cmservice.common.htcondor import HTCondorManager

    sub_file = Path(__file__).parent.parent / "fixtures/htcondor" / "htcondor_submit_file.sub"
    mgr = HTCondorManager()
    result = await mgr.submit_description_from_file(sub_file)
    assert result["should_transfer_files"] == "Yes"
