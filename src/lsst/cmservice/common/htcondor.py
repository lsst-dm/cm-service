"""Utility functions for working with htcondor jobs"""

from collections.abc import Mapping
from typing import Any

from anyio import Path, open_process
from anyio.streams.text import TextReceiveStream

from ..config import config
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


async def write_htcondor_script(
    htcondor_script_path: Path,
    htcondor_log: Path,
    script_url: Path,
    log_url: Path,
    **kwargs: Any,
) -> Path:
    """Write a submit wrapper script for htcondor

    Parameters
    ----------
    htcondor_script_path: anyio.Path
        Path for the wrapper file written by this function

    htcondor_log: anyio.Path
        Path for the wrapper log

    script_url: anyio.Path
        Script to submit

    log_url: anyio.Path
        Location of job log file to write

    Returns
    -------
    htcondor_log: str
        Path to the log wrapper log
    """
    options = dict(
        initialdir=config.htcondor.working_directory,
        batch_name=config.htcondor.batch_name,
        should_transfer_files="Yes",
        when_to_transfer_output="ON_EXIT",
        get_env=True,
        request_cpus=config.htcondor.request_cpus,
        request_memory=config.htcondor.request_mem,
        request_disk=config.htcondor.request_disk,
    )
    options.update(**kwargs)

    htcondor_script_contents = [
        f"executable = {script_url}",
        f"log = {htcondor_log}",
        f"output = {log_url}",
        f"error = {log_url}",
    ]
    for key, val in options.items():
        htcondor_script_contents.append(f"{key} = {val}")
    htcondor_script_contents.append("queue\n")

    await Path(htcondor_script_path).write_text("\n".join(htcondor_script_contents))
    return Path(htcondor_log)


async def submit_htcondor_job(
    htcondor_script_path: str | Path,
    fake_status: StatusEnum | None = None,
) -> None:
    """Submit a  `Script` to htcondor

    Parameters
    ----------
    htcondor_script_path: str | anyio.Path
        Path to the script to submit

    fake_status: StatusEnum | None,
        If set, don't actually submit the job

    """
    fake_status = fake_status or config.mock_status
    if fake_status is not None:
        return

    try:
        async with await open_process(
            [config.htcondor.condor_submit_bin, "-file", htcondor_script_path],
            env=build_htcondor_submit_environment(),
        ) as condor_submit:
            if await condor_submit.wait() != 0:  # pragma: no cover
                assert condor_submit.stderr
                stderr_msg = ""
                async for text in TextReceiveStream(condor_submit.stderr):
                    stderr_msg += text
                raise CMHTCondorSubmitError(f"Bad htcondor submit: f{stderr_msg}")

    except Exception as e:
        raise CMHTCondorSubmitError(f"Bad htcondor submit: {e}") from e


async def check_htcondor_job(
    htcondor_id: str | None,
    fake_status: StatusEnum | None = None,
) -> StatusEnum:
    """Check the status of a `HTCondor` job

    Parameters
    ----------
    htcondor_id : str | None
        htcondor job id, in this case the log file from the wrapper script

    fake_status: StatusEnum | None,
        If set, don't actually check the job and just return fake_status

    Returns
    -------
    status: StatusEnum
        HTCondor job status
    """
    fake_status = fake_status or config.mock_status
    if fake_status is not None:
        return StatusEnum.reviewable if fake_status.value >= StatusEnum.reviewable.value else fake_status
    try:
        if htcondor_id is None:  # pragma: no cover
            raise CMHTCondorCheckError("No htcondor_id")
        async with await open_process(
            [config.htcondor.condor_q_bin, "-userlog", htcondor_id, "-af", "JobStatus", "ExitCode"],
            env=build_htcondor_submit_environment(),
        ) as condor_q:  # pragma: no cover
            if await condor_q.wait() != 0:
                assert condor_q.stderr
                stderr_msg = ""
                async for text in TextReceiveStream(condor_q.stderr):
                    stderr_msg += text
                raise CMHTCondorCheckError(f"Bad htcondor check: {stderr_msg}")
            try:
                assert condor_q.stdout
                lines = ""
                async for text in TextReceiveStream(condor_q.stdout):
                    lines += text
                # condor_q puts an extra newline, we use 2nd to the last line
                tokens = lines.split("\n")[-2].split()
                assert len(tokens) == 2
                htcondor_status = int(tokens[0])
                exit_code = tokens[1]
            except Exception as e:
                raise CMHTCondorCheckError(f"Badly formatted htcondor check: {e}") from e
    except Exception as e:
        raise CMHTCondorCheckError(f"Bad htcondor check: {e}") from e

    status = htcondor_status_map[htcondor_status]  # pragma: no cover
    if status == StatusEnum.reviewable:  # pragma: no cover
        if int(exit_code) == 0:
            status = StatusEnum.accepted
        else:
            status = StatusEnum.failed
    return status  # pragma: no cover


def build_htcondor_submit_environment() -> Mapping[str, str]:
    """Construct an environment to apply to the subprocess shell when
    submitting an htcondor job.

    The condor job will inherit this specific environment via the submit file
    command `get_env = True`, so it must satisfy the requirements of any work
    being performed in the submitted job.

    This primarily means that if the job is to run a butler command, the
    necessary environment variables to support butler must be present; if the
    job is to run a bps command, the environment variables must support it.

    This also means that the environment constructed here is fundamentally
    different to the environment in which the service or daemon operates and
    should closer match the environment of an interactive sdfianaXXX user at
    SLAC.
    """
    return dict(
        CONDOR_CONFIG="ONLY_ENV",
        _CONDOR_CONDOR_HOST=config.htcondor.collector_host,
        _CONDOR_COLLECTOR_HOST=config.htcondor.collector_host,
        _CONDOR_SCHEDD_HOST=config.htcondor.schedd_host,
        _CONDOR_SEC_CLIENT_AUTHENTICATION_METHODS=config.htcondor.authn_methods,
        _CONDOR_DAGMAN_MANAGER_JOB_APPEND_GETENV=str(config.htcondor.dagman_job_append_get_env),
        DAF_BUTLER_REPOSITORY_INDEX=config.butler.repository_index,
        FS_REMOTE_DIR=config.htcondor.fs_remote_dir,
        HOME=config.htcondor.user_home,
        LSST_VERSION=config.bps.lsst_version,
        LSST_DISTRIB_DIR=config.bps.lsst_distrib_dir,
        # FIX: because there is no db-auth.yaml in lsstsvc1's home directory
        PGPASSFILE=f"{config.htcondor.user_home}/.lsst/postgres-credentials.txt",
        PGUSER=config.butler.default_username,
        PATH=(
            f"{config.htcondor.user_home}/.local/bin:{config.htcondor.user_home}/bin:{config.slurm.home}:"
            f"/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin"
        ),
    )
