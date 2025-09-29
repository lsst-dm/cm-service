"""Utility functions for working with bash scripts"""

import pathlib
import re
from collections import deque
from typing import Any

import yaml
from anyio import Path, open_file, open_process
from anyio.streams.text import TextReceiveStream
from jinja2 import Environment, PackageLoader

from ..config import config
from .enums import StatusEnum
from .errors import CMBashSubmitError


async def get_diagnostic_message(
    log_url: str | Path,
) -> str:
    """Read the last line of a log file as a diagnostic error message

    Parameters
    ----------
    log_url : `str` | `anyio.Path`
        The url of the log which may contain a diagnostic message

    Returns
    -------
    str
        The last line of the file, or an error message
    """
    log_path = Path(log_url)
    last_line: deque[str] = deque(maxlen=1)
    if not await log_path.exists():
        return f"ERROR Log file {log_url} does not exist"
    try:
        async with await open_file(log_url) as f:
            async for line in f:
                last_line.append(line)

        if last_line:
            return last_line.pop().strip()
        return "ERROR Empty log file"
    except Exception as e:
        return f"ERROR reading log file: {e}"


async def parse_bps_stdout(url: str | Path) -> dict[str, str]:
    """Parse the stdout from a bps submit job.

    Parameters
    ----------
    url : `str | anyio.Path`
        url for BPS submit stdout

    Returns
    -------
    out_dict `str`
        a dictionary containing the stdout from BPS submit
    """
    bps_stdout_parser = re.compile(r"^(?P<token>[\w\s]+):\s*(?P<value>.*)$", re.MULTILINE)
    out_dict = {}
    stdout = await Path(url).read_text()
    for match in re.finditer(bps_stdout_parser, stdout):
        out_dict[match.group("token")] = match.group("value")
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
    except Exception as e:
        msg = f"Bad bash submit: {e}"
        raise CMBashSubmitError(msg) from e
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
        msg = f"No script at path {script_url}"
        raise CMBashSubmitError(msg)

    script_command = await script_path.resolve()

    async with await open_process([script_command]) as process:
        await process.wait()
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
    values: dict,
    **kwargs: Any,
) -> Path:
    """Utility function to write a bash script for later execution.

    Parameters
    ----------
    script_url: `str | anyio.Path`
        Location to write the script

    command: `str`
        Main command line(s) in the script

    values: `dict`
        Mapping of potential template variables to values.

    Keywords
    --------
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
    # Get the yaml template using package lookup
    template_environment = Environment(loader=PackageLoader("lsst.cmservice"))
    bash_template = template_environment.get_template("legacy_wms_submit_sh.j2")

    fake = kwargs.get("fake")
    rollback_prefix = Path(kwargs.get("rollback", "."))

    script_path = rollback_prefix / script_url

    if fake:
        command = f"echo '{command}'"

    await script_path.parent.mkdir(parents=True, exist_ok=True)

    template_values = {
        "command": command,
        **values,
    }

    try:
        # Render bash script template to `script_path`
        bash_output = bash_template.render(template_values)
        await Path(script_path).write_text(bash_output)
    except Exception as e:
        msg = f"Error writing a script to run BPS job {script_url}; threw {e}"
        raise RuntimeError(msg)

    return script_path
