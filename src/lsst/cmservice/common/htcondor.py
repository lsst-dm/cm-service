"""Utility functions for working with htcondor jobs"""

import subprocess
from typing import Any

from .enums import StatusEnum
from .errors import CMHTCondorCheckError, CMHTCondorSubmitError

htcondor_status_map = {
    1: StatusEnum.running,
    2: StatusEnum.running,
    3: StatusEnum.running,
    4: StatusEnum.reviewable,
    5: StatusEnum.paused,
    6: StatusEnum.running,
    7: StatusEnum.running,
}


def write_htcondor_script(
    htcondor_script_path: str,
    htcondor_log: str,
    script_url: str,
    log_url: str,
    **kwargs: Any,
) -> str:
    """Write a submit wrapper script for htcondor

    Parameters
    ----------
    htcondor_script_path: str
        Path for the wrapper file written by this function

    htcondor_log: str
        Path for the wrapper log

    script_url: str
        Script to submit

    log_url: str
        Location of job log file to write

    Returns
    -------
    htcondor_log: str
        Path to the log wrapper log
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

    with open(htcondor_script_path, "w") as fout:
        fout.write(f"executable = {script_url}\n")
        fout.write(f"log = {htcondor_log}\n")
        fout.write(f"output = {log_url}\n")
        fout.write(f"error = {log_url}\n")
        for key, val in options.items():
            fout.write(f"{key} = {val}\n")
        fout.write("queue\n")
    return htcondor_log


def submit_htcondor_job(
    htcondor_script_path: str,
    fake_status: StatusEnum | None = None,
) -> None:
    """Submit a  `Script` to htcondor

    Parameters
    ----------
    htcondor_script_path: str
        Path to the script to submit

    fake_status: StatusEnum | None,
        If set, don't actually submit the job

    """
    if fake_status is not None:
        return
    try:
        with subprocess.Popen(
            [
                "condor_submit",
                htcondor_script_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as sbatch:
            sbatch.wait()
            if sbatch.returncode != 0:
                assert sbatch.stderr
                msg = sbatch.stderr.read().decode()
                raise CMHTCondorSubmitError(f"Bad htcondor submit: {msg}")
    except Exception as msg:
        raise CMHTCondorSubmitError(f"Bad htcondor submit: {msg}") from msg


def check_htcondor_job(
    htcondor_id: str,
    fake_status: StatusEnum | None = None,
) -> StatusEnum:
    """Check the status of a `HTCondor` job

    Parameters
    ----------
    htcondor_id : str
        htcondor job id, in this case the log file from the wrapper script

    fake_status: StatusEnum | None,
        If set, don't actually check the job and just return fake_status

    Returns
    -------
    status: StatusEnum
        HTCondor job status
    """
    if fake_status is not None:
        return StatusEnum.reviewable
    try:
        with subprocess.Popen(
            ["condor_q", "-userlog", htcondor_id, "-af", "JobStatus", "ExitCode"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as condor_q:
            condor_q.wait()
            if condor_q.returncode != 0:
                assert condor_q.stderr
                msg = condor_q.stderr.read().decode()
                raise CMHTCondorCheckError(f"Bad htcondor check: {msg}")
            try:
                assert condor_q.stdout
                lines = condor_q.stdout.read().decode().split("\n")
                # condor_q puts an extra newline, we use 2nd to the last line
                tokens = lines[-2].split()
                assert len(tokens) == 2
                htcondor_status = int(tokens[0])
                exit_code = tokens[1]
            except Exception as msg:
                raise CMHTCondorCheckError(f"Badly formatted htcondor check: {msg}")
    except Exception as msg:
        raise CMHTCondorCheckError(f"Bad htcondor check: {msg}")

    status = htcondor_status_map[htcondor_status]
    if status == StatusEnum.reviewable:
        if int(exit_code) == 0:
            status = StatusEnum.accepted
        else:
            status = StatusEnum.failed
    return status
