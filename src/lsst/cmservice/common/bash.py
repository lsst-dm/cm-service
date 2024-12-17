"""Utility functions for working with bash scripts"""

import subprocess
from pathlib import Path
from typing import Any

from fastapi.concurrency import run_in_threadpool

from ..common.utils import check_file_exists, read_lines, write_string, yaml_dump, yaml_safe_load
from ..config import config
from .enums import StatusEnum
from .errors import CMBashSubmitError


async def get_diagnostic_message(
    log_url: str,
) -> str:
    """Read the last line of a log file, aspirational hoping
    that it contains a diagnostic error message

    Parameters
    ----------
    log_url : `str`
        The url of the log which may contain a diagnostic message

    Returns
    -------
    The last line of the log file, potentially containing a diagnostic message.
    """
    if not await run_in_threadpool(check_file_exists, log_url):
        return f"Log file {log_url} does not exist"
    try:
        lines = await run_in_threadpool(read_lines, log_url)
        if lines:
            return lines[-1].strip()
        return "Empty log file"
    except Exception as e:
        return f"Error reading log file: {e}"


async def parse_bps_stdout(url: str) -> dict[str, str]:
    """Parse the std from a bps submit job. Wraps the synchronous function
    and passes to `fastapi.concurrency.run_in_threadpool`

    Parameters
    ----------
    url : `str`
        url for BPS submit stdout

    Returns
    -------
    out_dict `str`
        a dictionary containing the stdout from BPS submit
    """
    out_dict = await run_in_threadpool(sync_parse_bps_stdout, url)
    return out_dict


def sync_parse_bps_stdout(url: str) -> dict[str, str]:
    """Parse the std from a bps submit job. Synchronous function using
    standard readline. More work should be done to make this function work in
    the async world.

    Parameters
    ----------
    url : `str`
        url for BPS submit stdout

    Returns
    -------
    out_dict `str`
        a dictionary containing the stdout from BPS submit
    """
    out_dict = {}
    with open(url, encoding="utf8") as fin:
        line = fin.readline()
        while line:
            tokens = line.split(":")
            if len(tokens) != 2:  # pragma: no cover
                line = fin.readline()
                continue
            out_dict[tokens[0]] = tokens[1]
            line = fin.readline()
    return out_dict


async def run_bash_job(
    script_url: str,
    log_url: str,
    stamp_url: str,
    fake_status: StatusEnum | None = None,
) -> None:
    """Run a bash job. Most of the work is done in subprocesses run in a
    companion synchronous function, `sync_submit_file_to_run_in_bash`, which is
    wrapped in `fastapi.concurrency.run_in_threadpool`.

    Parameters
    ----------
    script_url: str
        Script to submit

    log_url: str
        Location of log file to write

    log_url: str
        Location of stamp file to write

    fake_status: StatusEnum | None,
        If set, don't actually submit the job
    """
    fake_status = fake_status or config.mock_status
    if fake_status is not None:
        with open(stamp_url, "w", encoding="utf-8") as fstamp:
            fields = dict(status=StatusEnum.reviewable.name)
            await run_in_threadpool(yaml_dump, fields, stamp_url)
        return
    try:
        await run_in_threadpool(sync_submit_file_to_run_in_bash, script_url, log_url)
    except Exception as msg:
        raise CMBashSubmitError(f"Bad bash submit: {msg}") from msg
    fields = dict(status="accepted")
    await run_in_threadpool(yaml_dump, fields, stamp_url)


def sync_submit_file_to_run_in_bash(script_url: str, log_url: str) -> None:
    """Make a script executable, then submit to run in bash. To be wrapped in
    `fastapi.concurrency.run_in_threadpool` by the asynchronous function above,
    `run_bash_job`. Just a quick attempt to wrap the process; more work should
    be done here to make this function async-friendly.

    Parameters
    ----------
    script_url : `str`
        Path to the script to run.
    log_url : `str`
        Path to output the logs.
    """
    with open(log_url, "w", encoding="utf-8") as fout:
        script_path = Path(script_url)
        if script_path.exists():
            script_path.chmod(0o755)
        else:
            raise CMBashSubmitError(f"No script at path {script_url}")
        with subprocess.Popen(
            [script_path.resolve()],
            stdout=fout,
            stderr=fout,
        ) as process:
            process.wait()
            if process.returncode != 0:  # pragma: no cover
                assert process.stderr
                msg = process.stderr.read().decode()
                raise CMBashSubmitError(f"Bad bash submit: {msg}")


async def check_stamp_file(
    stamp_file: str | None,
    default_status: StatusEnum,
) -> StatusEnum:
    """Check a 'stamp' file for a status code.

    Parameters
    ----------
    stamp_file: str | None
        File to read for status

    default_status: StatusEnum
        Status to return if stamp_file does not exist

    Returns
    -------
    status: StatusEnum
        Status of the script
    """
    if stamp_file is None:
        return default_status
    file_exists = await run_in_threadpool(check_file_exists, stamp_file)
    if not file_exists:
        return default_status
    fields = await run_in_threadpool(yaml_safe_load, stamp_file)
    return StatusEnum[fields["status"]]


async def write_bash_script(
    script_url: str,
    command: str,
    **kwargs: Any,
) -> Path:
    """Utility function to write a bash script for later execution.

    Parameters
    ----------
    script_url: `str`
        Location to write the script

    command: `str`
        Main command line(s) in the script

    Keywords
    --------
    prepend: `str | None`
        Text to prepend before command

    append: `str | None`
        Test to append after command

    stamp: `str | None`
        Text to echo to stamp file when script completes

    stamp_url: `str | None`
        Stamp file to write to when script completes

    fake: `str | None`
        Echo command instead of running it

    rollback: `str | Path | None`
        Prefix to script_url used when rolling back
        processing

    Returns
    -------
    script_url : `str`
        The path to the newly written script
    """
    prepend = kwargs.get("prepend")
    append = kwargs.get("append")
    fake = kwargs.get("fake")
    rollback_prefix = kwargs.get("rollback", "")

    if isinstance(rollback_prefix, Path):
        script_path = rollback_prefix / script_url
    else:
        script_path = Path(f"{rollback_prefix}{script_url}")
    script_path.parent.mkdir(parents=True, exist_ok=True)
    # I chose not to make the directory `with contextlib.suppress(OSError)`
    # because cm-service under-reports a lot of the issues it might run into
    # that we need to respond to better. I think most relevant situations will
    # be handled by `parents=True, exist_ok=True`, but will revert to the above
    # suppression if I am wrong.
    if fake:
        command = f"echo '{command}'"
    contents = (prepend if prepend else "") + "\n" + command + "\n" + (append if append else "")
    await run_in_threadpool(write_string, contents, script_path)
    return script_path
