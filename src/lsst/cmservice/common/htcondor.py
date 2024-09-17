"""Utility functions for working with htcondor jobs"""

import subprocess
from typing import Any

from .enums import StatusEnum
from .errors import CMHTCondorSubmitError

htcondor_status_map = {
    1: StatusEnum.running,
    2: StatusEnum.running,
    3: StatusEnum.running,
    4: StatusEnum.reviewable,
    5: StatusEnum.paused,
    6: StatusEnum.running,
    7: StatusEnum.running,
}


async def write_htcondor_script(
    htcondor_script: str,
    htcondor_log: str,
    script_url: str,
    log_url: str,
    **kwargs: Any,
) -> str:
    """Write a submit wrapper script for htcondor

    Parameters
    ----------
    htcondor_script: str
        Path for the wrapper file

    htcondor_log: str
        Path for the wrapper log

    script_url: str
        Script to submit

    log_url: str
        Location of job log file to write
    """
    options = dict(
        should_transfer_files="Yes",
        when_to_transfer_output="ON_EXIT",
        get_env=True,
        request_cpus=1,
        request_memory="512M",
        request_disk="1G",
    )
    options.update(**kwargs)

    with open(htcondor_script, "w") as fout:
        fout.write(f"executable = {script_url}\n")
        fout.write(f"log = {htcondor_log}\n")
        fout.write(f"output = {log_url}\n")
        fout.write(f"error = {log_url}\n")
        for key, val in options.items():
            fout.write(f"{key} = {val}\n")
        fout.write("queue\n")
    return htcondor_log


async def submit_htcondor_job(
    htcondor_script: str,
) -> None:
    """Submit a  `Script` to htcondor

    Parameters
    ----------
    htcondor_script: str
        Script to submit

    """
    try:
        with subprocess.Popen(
            [
                "condor_submit",
                htcondor_script,
            ],
            stdout=subprocess.PIPE,
        ) as sbatch:
            assert sbatch.stdout
    except TypeError as msg:
        raise CMHTCondorSubmitError(f"Bad htcondor submit: {msg}") from msg


async def check_htcondor_job(
    htcondor_id: str,
) -> StatusEnum:
    """Check the status of a `HTConddor` job

    Parameters
    ----------
    htcondor_id : str
        htcondor job id

    Returns
    -------
    status: StatusEnum
        HTCondor job status
    """
    with subprocess.Popen(
        ["condor_q", "-userlog", htcondor_id, "-af", "JobStatus", "ExitCode"],
        stdout=subprocess.PIPE,
    ) as condor_q:
        assert condor_q.stdout
        lines = condor_q.stdout.read().decode().split("\n")
        # condor_q puts an extra newline, so we use the second to the last line
        tokens = lines[-2].split()
        assert len(tokens) == 2
        htcondor_status = int(tokens[0])
        exit_code = tokens[1]
        status = htcondor_status_map[htcondor_status]
        if status == StatusEnum.reviewable:
            if int(exit_code) == 0:
                status = StatusEnum.accepted
            else:
                status = StatusEnum.failed
        return status
