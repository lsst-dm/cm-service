"""Utility functions for working with slurm jobs"""

import subprocess

from .enums import StatusEnum
from .errors import CMSlurmCheckError, CMSlurmSubmitError

slurm_status_map = {
    "BOOT_FAIL": StatusEnum.failed,
    "CANCELLED": StatusEnum.failed,
    "COMPLETED": StatusEnum.accepted,
    "CONFIGURING": StatusEnum.running,
    "COMPLETING": StatusEnum.running,
    "DEADLINE": StatusEnum.failed,
    "FAILED": StatusEnum.failed,
    "NODE_FAIL": StatusEnum.failed,
    "NOT_SUBMITTED": StatusEnum.prepared,
    "OUT_OF_MEMORY": StatusEnum.failed,
    "PENDING": StatusEnum.running,
    "PREEMPTED": StatusEnum.running,
    "RUNNING": StatusEnum.running,
    "RESV_DEL_HOLD": StatusEnum.running,
    "REQUEUE_FED": StatusEnum.running,
    "REQUEUE_HOLD": StatusEnum.running,
    "REQUEUED": StatusEnum.running,
    "RESIZING": StatusEnum.running,
    "REVOKED": StatusEnum.failed,
    "SIGNALING": StatusEnum.running,
    "SPECIAL_EXIT": StatusEnum.failed,
    "STAGE_OUT": StatusEnum.running,
    "STOPPED": StatusEnum.running,
    "SUSPENDED": StatusEnum.running,
    "TIMEOUT": StatusEnum.failed,
}


def submit_slurm_job(
    script_url: str,
    log_url: str,
) -> str:
    """Submit a  `Script` to slurm

    Parameters
    ----------
    script_url: str
        Script to submit

    log_url: str
        Location of log file to write

    Returns
    -------
    job_id : str
        Slurm job id
    """
    try:
        with subprocess.Popen(
            [
                "sbatch",
                "-o",
                log_url,
                "--mem",
                "16448",
                "--account",
                "rubin:production",
                "-p",
                "milano",
                "--parsable",
                script_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as sbatch:
            sbatch.wait()
            if sbatch.returncode != 0:
                assert sbatch.stderr
                msg = sbatch.stderr.read().decode()
                raise CMSlurmSubmitError(f"Bad slurm submit: {msg}")
            assert sbatch.stdout
            line = sbatch.stdout.read().decode().strip()
            return line.split("|")[0]
    except TypeError as msg:
        raise CMSlurmSubmitError(f"Bad slurm submit: {msg}") from msg


def check_slurm_job(
    slurm_id: str | None,
) -> StatusEnum | None:
    """Check the status of a `Slurm` job

    Parameters
    ----------
    slurm_id : str
        Slurm job id

    Returns
    -------
    status: StatusEnum | None
        Slurm job status, None implies job not found in slurm
    """
    if slurm_id is None:
        return None
    with subprocess.Popen(["sacct", "--parsable", "-b", "-j", slurm_id], stdout=subprocess.PIPE) as sacct:
        sacct.wait()
        if sacct.returncode != 0:
            assert sacct.stderr
            msg = sacct.stderr.read().decode()
            raise CMSlurmCheckError(f"Bad slurm check: {msg}")
        try:
            assert sacct.stdout
            lines = sacct.stdout.read().decode().split("\n")
            if len(lines) < 2:
                return slurm_status_map["PENDING"]
            tokens = lines[1].split("|")
            if len(tokens) < 2:
                return slurm_status_map["PENDING"]
            slurm_status = tokens[1]
        except Exception as msg:
            raise CMSlurmCheckError(f"Badly formatted slurm check: {msg}")
        return slurm_status_map[slurm_status]
