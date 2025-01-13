"""Utility functions for working with bash scripts"""

import pathlib
from collections import deque
from typing import Any

import yaml
from anyio import Path, open_file, open_process
from anyio.streams.text import TextReceiveStream

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
    log_path = Path(log_url)
    last_line: deque[str] = deque(maxlen=1)
    if not await log_path.exists():
        return f"Log file {log_url} does not exist"
    try:
        async with await open_file(log_url) as f:
            async for line in f:
                last_line.append(line)

        if last_line:
            return last_line.pop().strip()
        return "Empty log file"
    except Exception as e:
        return f"Error reading log file: {e}"


async def parse_bps_stdout(url: str) -> dict[str, str]:
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
    async with await open_file(url, encoding="utf8") as f:
        async for line in f:
            tokens = line.split(":")
            if len(tokens) != 2:  # pragma: no cover
                continue
            out_dict[tokens[0]] = tokens[1]
    return out_dict


async def run_bash_job(
    script_url: str | Path,
    log_url: str,
    stamp_url: str | Path,
    fake_status: StatusEnum | None = None,
) -> None:
    """Run a bash job and write a "stamp file" with the value of the script's
    resulting status.

    Parameters
    ----------
    script_url: str
        Script to submit

    log_url: str
        Location of log file to write

    stamp_url: str | anyio.Path
        Location of stamp file to write

    fake_status: StatusEnum | None,
        If set, don't actually submit the job
    """
    fake_status = fake_status or config.mock_status
    if fake_status is not None:
        yaml_output = yaml.dump(dict(status=StatusEnum.reviewable.name))
        await Path(stamp_url).write_text(yaml_output)
        return
    try:
        await submit_file_to_run_in_bash(script_url, log_url)
    except Exception as msg:
        raise CMBashSubmitError(f"Bad bash submit: {msg}") from msg
    fields = dict(status=StatusEnum.accepted.name)
    yaml_output = yaml.dump(fields)
    await Path(stamp_url).write_text(yaml_output)


async def submit_file_to_run_in_bash(script_url: str | Path, log_url: str | pathlib.Path) -> None:
    """Make a script executable, then submit to run in bash.

    Parameters
    ----------
    script_url : `str | anyio.Path`
        Path to the script to run. Must be or will be cast as an async Path.
    log_url : `str | pathlib.Path`
        Path to output the logs. Must be or will be case as a sync Path.
    """
    script_path = Path(script_url)
    log_path = Path(log_url)

    if await script_path.exists():
        await script_path.chmod(0o755)
    else:
        raise CMBashSubmitError(f"No script at path {script_url}")

    script_command = await script_path.resolve()

    async with await open_process([script_command]) as process:
        assert process.stdout
        assert process.stderr
        async with await open_file(log_path, "w") as log_out:
            async for text in TextReceiveStream(process.stdout):
                await log_out.write(text)
            async for text in TextReceiveStream(process.stderr):
                await log_out.write(text)
        if process.returncode != 0:  # pragma: no cover
            raise CMBashSubmitError("Bad bash submit, check log file.")


async def check_stamp_file(
    stamp_file: str | Path | None,
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
    stamp_file = Path(stamp_file)
    if not await stamp_file.exists():
        return default_status
    stamp = await Path(stamp_file).read_text()
    fields = yaml.safe_load(stamp)
    return StatusEnum[fields["status"]]


async def write_bash_script(
    script_url: str | Path,
    command: str,
    **kwargs: Any,
) -> Path:
    """Utility function to write a bash script for later execution.

    Parameters
    ----------
    script_url: `str | anyio.Path`
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
        processing. Will default to CWD (".").

    Returns
    -------
    script_url : `anyio.Path`
        The path to the newly written script
    """
    prepend = kwargs.get("prepend")
    append = kwargs.get("append")
    fake = kwargs.get("fake")
    rollback_prefix = Path(kwargs.get("rollback", "."))

    script_path = rollback_prefix / script_url

    if fake:
        command = f"echo '{command}'"

    await script_path.parent.mkdir(parents=True, exist_ok=True)
    contents = (prepend if prepend else "") + "\n" + command + "\n" + (append if append else "")

    async with await open_file(script_path, "w") as fout:
        await fout.write(contents)
    return script_path
