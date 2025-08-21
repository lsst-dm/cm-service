"""Utility functions for working with slurm jobs"""

from anyio import Path, open_process
from anyio.streams.text import TextReceiveStream

from ..config import config
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


async def submit_slurm_job(
    script_url: str | Path,
    log_url: str | Path,
    fake_status: StatusEnum | None = None,
) -> str:
    """Submit a  `Script` to slurm

    Parameters
    ----------
    script_url: str | anyio.Path
        Script to submit

    log_url: str | anyio.Path
        Location of log file to write

    fake_status: StatusEnum | None,
        If set, don't actually submit the job

    Returns
    -------
    job_id : str
        Slurm job id
    """
    fake_status = fake_status or config.mock_status
    if fake_status is not None:
        return "fake_job"
    try:
        async with await open_process(
            [
                f"{config.slurm.home}/sbatch",
                "-o",
                log_url,
                "--mem",
                config.slurm.memory,
                "--account",
                config.slurm.account,
                "-p",
                config.slurm.partition,
                "--parsable",
                script_url,
            ],
        ) as slurm_submit:  # pragma: no cover
            await slurm_submit.wait()
            if slurm_submit.returncode != 0:
                assert slurm_submit.stderr
                stderr_msg = ""
                async for text in TextReceiveStream(slurm_submit.stderr):
                    stderr_msg += text
                raise CMSlurmSubmitError(f"Bad slurm submit: {stderr_msg}")
            assert slurm_submit.stdout
            stdout_msg = ""
            async for text in TextReceiveStream(slurm_submit.stdout):
                stdout_msg += text
            return stdout_msg.split("|")[0]
    except Exception as e:
        raise CMSlurmSubmitError(f"Bad slurm submit: {e}") from e


async def check_slurm_job(
    slurm_id: str | None,
    fake_status: StatusEnum | None = None,
) -> StatusEnum:
    """Check the status of a `Slurm` job

    Parameters
    ----------
    slurm_id : str
        Slurm job id

    fake_status: StatusEnum | None,
        If set, don't actually check the job and just return fake_status

    Returns
    -------
    status: StatusEnum
        Slurm job status
    """
    if fake_status is not None:
        return StatusEnum.reviewable if fake_status.value >= StatusEnum.reviewable.value else fake_status
    if slurm_id is None:  # pragma: no cover
        return StatusEnum.running
    try:
        async with await open_process(
            [f"{config.slurm.home}/sacct", "--parsable", "-b", "-j", slurm_id]
        ) as slurm_check:  # pragma: no cover
            await slurm_check.wait()
            if slurm_check.returncode != 0:
                assert slurm_check.stderr
                stderr_msg = ""
                async for text in TextReceiveStream(slurm_check.stderr):
                    stderr_msg += text
                raise CMSlurmCheckError(f"Bad slurm check: {stderr_msg}")
            try:
                assert slurm_check.stdout
                stdout_msg = ""
                async for text in TextReceiveStream(slurm_check.stdout):
                    stdout_msg += text
                lines = stdout_msg.split("\n")
                if len(lines) < 2:
                    return slurm_status_map["PENDING"]
                tokens = lines[1].split("|")
                if len(tokens) < 2:
                    return slurm_status_map["PENDING"]
                slurm_status = tokens[1]
            except Exception as e:
                raise CMSlurmCheckError(f"Badly formatted slurm check: {e}") from e
    except Exception as e:
        raise CMSlurmCheckError(f"Bad slurm check: {e}") from e
    return slurm_status_map[slurm_status]  # pragma: no cover
