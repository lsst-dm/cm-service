"""Utility functions for working with htcondor jobs"""

import importlib.util
import json
import sys
from collections.abc import Mapping
from types import ModuleType
from typing import Any

from anyio import Path, open_process
from anyio.streams.text import TextReceiveStream

from ..config import config
from .enums import StatusEnum
from .errors import CMHTCondorCheckError, CMHTCondorSubmitError
from .logging import LOGGER
from .panda import get_panda_token

logger = LOGGER.bind(module=__name__)


htcondor_status_map = {
    1: StatusEnum.running,
    2: StatusEnum.running,
    3: StatusEnum.reviewable,
    4: StatusEnum.reviewable,
    5: StatusEnum.blocked,
    6: StatusEnum.running,
    7: StatusEnum.paused,
}
"""Mapping of HTCondor JobStatus integer values to CM Service status enums.

HTCondor JobStatus may be idle (1), running (2), removing (3), completed (4),
held (5), transferring_output (6), or suspended (7).

A terminal status is mapped to reviewable here because the job's exit code
will ultimately determine whether the job is accepted or failed.
"""


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
            raise CMHTCondorCheckError("Bad htcondor check input: No htcondor_id")
        async with await open_process(
            [
                config.htcondor.condor_q_bin,
                "-userlog",
                htcondor_id,
                "-json",
                "-attributes",
                "JobStatus,ExitCode",
            ],
            env=build_htcondor_submit_environment(),
        ) as condor_q:  # pragma: no cover
            if await condor_q.wait() != 0:
                assert condor_q.stderr
                stderr_msg = ""
                async for text in TextReceiveStream(condor_q.stderr):
                    stderr_msg += text
                logger.error("Bad htcondor check", stderr=stderr_msg)
                raise CMHTCondorCheckError(f"Bad htcondor check: {stderr_msg}")
            try:
                assert condor_q.stdout
                lines = ""
                async for text in TextReceiveStream(condor_q.stdout):
                    lines += text
                htcondor_stdout: list[dict[str, Any]] = json.loads(lines)
                htcondor_status = htcondor_stdout[-1]["JobStatus"]
                exit_code = htcondor_stdout[-1].get("ExitCode")
            except (AssertionError, json.JSONDecodeError, IndexError, KeyError) as e:
                raise CMHTCondorCheckError(f"Badly formatted htcondor check: {e}") from e
    # FIXME the bare exception here is not great but the list of possible
    #       conditions is long.
    except Exception:
        logger.exception()
        return StatusEnum.failed

    status = htcondor_status_map[htcondor_status]  # pragma: no cover
    if status is StatusEnum.reviewable:  # pragma: no cover
        if (exit_code is not None) and (int(exit_code) == 0):
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

    Notes
    -----
    TODO use all configured htcondor config settings
    - `condor_environment = config.htcondor.model_dump(by_alias=True)`
    TODO we should not always use the same schedd host. We could get a list
         of all schedds from the collector and pick one at random.
    """

    # FIXME / TODO
    # This is nothing to do with htcondor vs panda as a WMS, but because CM
    # uses htcondor as its primary script-running engine for bps workflows even
    # if that workflow uses panda. Because of this, we need to also serialize
    # all of the panda environmental config for the subprocess to pick up.
    # We do this instead of delegating panda config to some arbitrary bash
    # script elsewhere in the filesystem whose only job is to set these env
    # vars for panda. This also allows us to provide our specific panda idtoken
    # as an env var instead of requiring the target process to pick it up from
    # some .token file that may or may not be present or valid.

    # calling the panda refresh token operation is a noop if no panda token is
    # present or if the panda token does not need to be refreshed yet.
    _ = get_panda_token()
    # TODO it could be worthwhile to put the panda check/refresh logic in the
    #      serializer method of the idtoken field.

    # Access AWS credentials dynamically
    # s = boto3.session.Session(profile_name=...)  # noqa: ERA001
    # url = s.client("s3").meta.endpoint_url  # noqa: ERA001
    # creds = s.get_credentials().get_frozen_credentials()  # noqa: ERA001
    # assert creds is not None
    # AWS_ACCESS_KEY_ID=creds.access_key  # noqa: ERA001
    # AWS_SECRET_ACCESS_KEY=creds.secret_key  # noqa: ERA001
    # construct url -> "scheme://access-key:secret-key@endpoint"

    return config.panda.model_dump(by_alias=True, exclude_none=True) | dict(
        CONDOR_CONFIG=config.htcondor.config_source,
        _CONDOR_CONDOR_HOST=config.htcondor.collector_host,
        _CONDOR_COLLECTOR_HOST=config.htcondor.collector_host,
        _CONDOR_SCHEDD_HOST=config.htcondor.schedd_host,
        _CONDOR_SEC_CLIENT_AUTHENTICATION_METHODS=config.htcondor.authn_methods,
        _CONDOR_DAGMAN_MANAGER_JOB_APPEND_GETENV="True",
        FS_REMOTE_DIR=config.htcondor.fs_remote_dir,
        # FIXME: populate the DAF_BUTLER_REPOSITORIES env var with the JSON
        #        string repr of the repository index as known to the service
        DAF_BUTLER_REPOSITORY_INDEX=config.butler.repository_index,
        HOME=config.htcondor.remote_user_home,
        LSST_VERSION=config.bps.lsst_version,
        LSST_DISTRIB_DIR=config.bps.lsst_distrib_dir,
        # FIXME: because the aws credentials file is assumed to be in place;
        #        the s3 resource supports a custom but nonstandard environment
        #        variable LSST_RESOURCES_S3_PROFILE_<profile> that can contain
        #        a https://<access key ID>:<secretkey>@<s3 endpoint hostname>;
        #        if this is a string we can build dynamically then we could use
        #        it instead of the following assertion
        AWS_SHARED_CREDENTIALS_FILE=f"{config.htcondor.remote_user_home}/.lsst/aws-credentials.ini",
        # FIXME: if we're going to go by AWS profiles, then we should maintain
        #        a config file with properly configured endpoint URLs -or-
        #        at least use the standard one(s)!
        # FIXME: make aws config values a separate parameters object
        # FIXME: the AWS endpoint should be based on the target profile of the
        #        butler, else a global endpoint value must satisfy all daemon
        #        instance butlers
        # FIXME: need to exclude None for the following!
        AWS_ENDPOINT_URL_S3=config.aws_s3_endpoint_url or "",
        AWS_REQUEST_CHECKSUM_CALCULATION="WHEN_REQUIRED",
        AWS_RESPONSE_CHECKSUM_VALIDATION="WHEN_REQUIRED",
        # FIXME: because there is no db-auth.yaml in lsstsvc1's home directory
        PGPASSFILE=f"{config.htcondor.remote_user_home}/.lsst/postgres-credentials.txt",
        # FIXME: the user is part of the credentials file, we should not need
        #        it in the env as well!
        PGUSER=config.butler.default_username,
        PATH=(
            f"{config.htcondor.remote_user_home}/.local/bin:{config.htcondor.remote_user_home}/bin:{config.slurm.home}:"
            f"/usr/local/bin:/usr/bin:/usr/local/sbin:/usr/sbin"
        ),
    )


def import_htcondor() -> ModuleType | None:
    """Import and return the htcondor module if it is available. Ensure the
    the current configuration is loaded.
    """
    if (htcondor := sys.modules.get("htcondor")) is not None:
        pass
    elif (importlib.util.find_spec("htcondor")) is not None:
        htcondor = importlib.import_module("htcondor")

    if htcondor is None:
        logger.warning("HTcondor not available.")
        return None

    htcondor.reload_config()

    return htcondor
