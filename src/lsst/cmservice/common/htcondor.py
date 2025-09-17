"""Utility functions for working with htcondor jobs"""

import importlib.util
import json
import random
import sys
from collections.abc import Mapping
from types import ModuleType
from typing import TYPE_CHECKING, Any

from anyio import Path, open_process
from anyio.streams.text import TextReceiveStream

from ..config import config
from .enums import StatusEnum
from .errors import CMHTCondorCheckError, CMHTCondorSubmitError
from .launchers import LauncherCheckResponse, LaunchManager
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
                msg = f"Bad htcondor submit: f{stderr_msg}"
                raise CMHTCondorSubmitError(msg)

    except Exception as e:
        msg = f"Bad htcondor submit: {e}"
        raise CMHTCondorSubmitError(msg) from e


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
                msg = f"Bad htcondor check: {stderr_msg}"
                raise CMHTCondorCheckError(msg)
            try:
                assert condor_q.stdout
                lines = ""
                async for text in TextReceiveStream(condor_q.stdout):
                    lines += text
                htcondor_stdout: list[dict[str, Any]] = json.loads(lines)
                htcondor_status = htcondor_stdout[-1]["JobStatus"]
                exit_code = htcondor_stdout[-1].get("ExitCode")
            except (AssertionError, json.JSONDecodeError, IndexError, KeyError) as e:
                msg = f"Badly formatted htcondor check: {e}"
                raise CMHTCondorCheckError(msg) from e
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


class HTCondorManager(LaunchManager):
    """A Launch Manager for HTCondor Jobs. Allows the execution of node scripts
    during state transitions.
    """

    collector: Any | None
    schedd: Any | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._htcondor: ModuleType | None = import_htcondor()
        if self._htcondor is not None:
            self.collector = self._htcondor.Collector(config.htcondor.collector_host)
        else:
            self.collector = None
        self.schedd = None

    async def submit_description_from_file(self, submission_spec: str | Path) -> dict[str, str]:
        """Given an htcondor submit description file, parse it into a dict
        representation of key-value pair strings.
        """
        if TYPE_CHECKING:
            assert self._htcondor is not None

        submit_dict = {}
        if isinstance(submission_spec, Path):
            submission_spec = await submission_spec.read_text()

        for line in submission_spec.splitlines():
            # each line should be some variation of key = value except a final
            # queue command
            if "=" not in line:
                continue
            k, v = line.split("=")
            submit_dict[k.strip()] = v.strip()

        return submit_dict

    def get_token(self) -> None:
        """Request an HTCondor authentication token."""
        # Careful, the TokenRequest interface is blocking
        ...

    def select_schedd(self) -> None:
        """Determine a schedd host to use with this instance of an HTCondor
        Manager.
        """
        if self._htcondor is None or self.collector is None:
            return None

        # TODO make async with anyio run_thread?
        schedds = self.collector.locateAll(self._htcondor.DaemonTypes.Schedd)

        # the schedd to which we submit a job is randomly chosen from the list
        self.schedd = self._htcondor.Schedd(random.choice(schedds))

    async def submit_ad(self, submission_spec: Path | dict | str) -> Any | None:
        """Submits a job ad to the currently selected schedd and returns the
        job reference which includes the cluster id.

        If anything goes wrong, returns None.

        Raises
        ------
        FileNotFoundError
            If the executable indicated by the submission file does not exist.
        """
        if self._htcondor is None or self.collector is None:
            return None

        # Ensure we have obtained a Schedd ad from the collector
        self.select_schedd()

        if self.schedd is None:
            return None

        # Parse the submit description file as a dictionary for "easier"
        # manipulation. The file would have been generated during a Node's
        # prepare trigger. We want it as a dict instead so we can directly
        # manipulate it without complicated string methods.
        if not isinstance(submission_spec, dict):
            submission_spec = await self.submit_description_from_file(submission_spec)

        # Set the htcondor config in the submission environment
        # The environment command in the submit file is a double-quoted,
        # whitespace-delimited list of name=value pairs where literal quotes
        # are doubled ("" or '').
        submission_environment = " ".join(
            [f"{k}={v}" for k, v in build_htcondor_submit_environment().items()]
        )
        submission_spec["environment"] = f'"{submission_environment}"'
        submission_spec["getenv"] = "False"

        # TODO some nodes may be too "heavy" for local universe execution.
        #      if not otherwise specified, use the local universe.
        if "universe" not in submission_spec:
            submission_spec["universe"] = "local"

        # Check for the existence and executability of the executable
        executable = Path(submission_spec["executable"])
        if await executable.exists():
            await executable.chmod(0o755)
        else:
            msg = f"Launch Manager cannot locate {str(executable)}"
            raise FileNotFoundError(msg)

        submit_ad = self._htcondor.Submit(submission_spec)
        cluster_id = self.schedd.submit(submit_ad)
        # TODO should log the schedd name and cluster id for reference. It's
        # probably not a bad idea to persist these metadata in the launch
        # just to have it available; it should agree with the same metdata
        # gathered in the check method when the event log is parsed.
        return cluster_id

    async def check(self, cluster_id: int, condor_log: Path) -> LauncherCheckResponse:
        """Using the cluster_id or the htcondor log file, check job status.

        This launcher method should be invoked by a Node Machine during its
        equivalent of a `is_successful` check, i.e., for determining whether
        the machine may transition from a running to a terminal state.

        Parameters
        ----------
        cluster_id : int
            The integer number of the htcondor job cluster id as provided in a
            ``htcondor.SubmitResult`` object and stored with the campaign node.
            If the cluster_id is greater than 0, then it may be used to ident-
            ify entries in the HTCondor job log. Otherwise, the job log entries
            may not disambiguate between multiple cluster_ids in the same log.

        Returns
        -------
        ``lsst.cmservice.common.launcher.LauncherCheckResponse``
            This method should only return True if the Job is successful and
            the return value/exit code is 0. It should return False if the job
            is not complete. Otherwise, it should raise an exception for the
            Node Machine to handle.

        Raises
        ------
        RuntimeError
            Raised when a error is encountered. Errors may include inability
            to import required packages or when error conditions are encounter-
            ed during the check. For HTCondor event log parsing, any abnormal
            termination or job abend (held, aborted, removal) will raise an
            exception. This exception should be eventually handled by the Node
            state machine's error handler (therefore should be reraised if
            caught anywhere else).
        """
        response = LauncherCheckResponse(success=False)

        # TODO it would be nice if this method returned a richer value so the
        # calling Node could reflect more job information in its metadata. Esp-
        # ecially with the EXECUTE event, pass back the event time and host;
        # and for abnormal termination the exit code could be useful.
        if self._htcondor is None or self.collector is None:
            msg = "HTCondor is not available or cannot be imported"
            raise RuntimeError(msg)

        # Using htcondor.JobEventLog with the userlog specified in the job
        # submit ad, we can approximate the `condor_q -userlog` command without
        # querying job history from the schedd. This limits us to what we can
        # understand about the job through a JobEvent entry, which is quite
        # limited compared to a Job ClassAd we could get from the schedd.
        # FIXME the JobEventLog raises an HTCondorIOError if the eventlog can't
        # be found. We should check its existence first, although the eventlog
        # is meant to be "touched" by the schedd as soon as the submit goes
        # through (i.e., a 0-byte file should be present).
        logger.debug(
            "Checking HTCondor Log for Launch Events", cluster_id=cluster_id, job_event_log=str(condor_log)
        )
        job_event_log = self._htcondor.JobEventLog(str(condor_log))

        for event in job_event_log.events(stop_after=0):
            # make sure the event is related to our job; if the provided
            # cluster id is 0, then we do not try to disambiguate job events.
            if (cluster_id > 0 and event.cluster != cluster_id) or event.proc != 0:
                continue

            match event.type:
                case self._htcondor.JobEventType.JOB_TERMINATED:
                    normal_termination = event.get("TerminatedNormally", False)
                    return_value = event.get("ReturnValue", -1)

                    if normal_termination and return_value == 0:
                        # Job succeeded
                        msg = "Job Normally Terminated"
                        logger.debug(msg, cluster_id=cluster_id, return_value=return_value)
                        response.success = True
                    elif normal_termination:
                        # Job failed successfully
                        msg = "Job Abnormally Terminated"
                        logger.debug(msg, cluster_id=cluster_id, return_value=return_value)
                        raise RuntimeError(msg)
                    else:
                        # Job failed unsuccessfully
                        signal = event.get("TerminatedBySignal", "<Unknown>")
                        msg = f"Job terminated on signal {signal}"
                        logger.debug(msg, cluster_id=cluster_id)
                        raise RuntimeError(msg)
                case self._htcondor.JobEventType.JOB_ABORTED:
                    msg = "Job was aborted"
                    logger.error(msg, cluster_id=cluster_id)
                    raise RuntimeError(msg)
                case self._htcondor.JobEventType.JOB_HELD:
                    # TODO raise an exception the Node Machine can recognize as
                    # requiring a transition to the blocked state instead of
                    # failed.
                    msg = "Job has been held"
                    logger.error(msg, cluster_id=cluster_id)
                    raise RuntimeError(msg)
                case self._htcondor.JobEventType.CLUSTER_REMOVE:
                    msg = "Job has been removed"
                    logger.error(msg, cluster_id=cluster_id)
                    raise RuntimeError(msg)
                case self._htcondor.JobEventType.EXECUTE:
                    host = event.get("ExecuteHost", "Unknown")
                    timestamp = event.get("EventTime", None)
                    msg = f"Job has been executed on {host} at {timestamp}"
                    logger.info(msg, cluster_id=cluster_id)
                    response.job_id = event.cluster
                    if timestamp is not None:
                        response.timestamp = timestamp
                    response.metadata_["execute_host"] = host
                    continue
                case _:
                    # Proceed past any non-terminal event in the log
                    logger.debug(
                        "Skipping non-terminal event in event log",
                        cluster_id=cluster_id,
                        event_type=event.type,
                    )
                    continue
        logger.debug(
            "Finished reading HTCondor Launcher Event Log",
            cluster_id=cluster_id,
            outcome=response.model_dump_json(),
        )
        return response

    async def launch(self, submission_spec: Path | dict | str) -> int:
        """Main entrypoint for a LaunchManager instance.

        The prepared submission file is sent to HTCondor and a SubmitResult is
        returned, which includes the job's ``cluster_id`` (an int).

        Parameters
        ----------
        submission_spec : Path | dict | str
            An HTCondor submission description, as a Path to such a file, a
            dictionary of k-v pairs, or a string literal.

        Raises
        ------
        RuntimeError
            If no job id is returned by the HTCondor Submit method, indicating
            a failure to submit.

        Returns
        -------
        int
            The HTCondor job cluster ID as an integer.
        """
        job_id = await self.submit_ad(submission_spec)
        if job_id is None:
            msg = "No submit result returned from htcondor"
            raise RuntimeError(msg)
        return job_id.cluster()
