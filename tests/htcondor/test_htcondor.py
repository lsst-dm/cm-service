import sys
from unittest.mock import Mock, patch

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

    held_log = Path(__file__).parent.parent / "fixtures/logs" / "job_held.condorlog"
    mgr = HTCondorManager()
    with pytest.raises(RuntimeError):
        result = await mgr.check(cluster_id=1094571, condor_log=held_log)

    bad_log = Path(__file__).parent.parent / "fixtures/logs" / "job_bad.condorlog"
    mgr = HTCondorManager()
    with pytest.raises(RuntimeError):
        result = await mgr.check(cluster_id=1323590, condor_log=bad_log)


async def test_sub_file_parsing() -> None:
    """Tests the generation of an htcondor submit description dictionary from
    a sub file.
    """
    from lsst.cmservice.common.htcondor import HTCondorManager

    sub_file = Path(__file__).parent.parent / "fixtures/htcondor" / "htcondor_submit_file.sub"
    mgr = HTCondorManager()
    result = await mgr.submit_description_from_file(sub_file)
    assert result["should_transfer_files"] == "Yes"


@patch("lsst.cmservice.common.htcondor.get_panda_token", return_value=None)
async def test_htcondor_environment_generation(mock_token: Mock) -> None:
    """Tests the generation of an htcondor submit environment string"""
    from lsst.cmservice.common.htcondor import build_htcondor_submit_environment
    from lsst.cmservice.config import config

    submit_env = build_htcondor_submit_environment()
    assert submit_env["HOME"] == config.htcondor.remote_user_home

    submit_env_items = [f"{k}={v}" for k, v in submit_env.items() if v != ""]
    assert f"HOME={config.htcondor.remote_user_home}" in submit_env_items

    submit_env_string = " ".join(submit_env_items)
    assert f" HOME={config.htcondor.remote_user_home} " in submit_env_string
