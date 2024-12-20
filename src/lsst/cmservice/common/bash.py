"""Utility functions for working with bash scripts"""

import contextlib
import os
import subprocess
from typing import Any

import yaml

from .enums import StatusEnum
from .errors import CMBashSubmitError


async def get_diagnostic_message(
    log_url: str,
) -> str:
    """Read the last line of a log file, aspirational hoping
    that it contains a diagnostic error message"""
    with open(log_url, encoding="utf-8") as fin:
        lines = fin.readlines()
        if lines:
            return lines[-1].strip()
        return "Empty log file"


def parse_bps_stdout(url: str) -> dict[str, str]:
    """Parse the std from a bps submit job"""
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


def run_bash_job(
    script_url: str,
    log_url: str,
    stamp_url: str,
    fake_status: StatusEnum | None = None,
) -> None:
    """Run a bash job

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
    if fake_status is not None:
        with open(stamp_url, "w", encoding="utf-8") as fstamp:
            fields = dict(status="reviewable")
            yaml.dump(fields, fstamp)
        return
    try:
        with open(log_url, "w", encoding="utf-8") as fout:
            os.system(f"chmod +x {script_url}")
            with subprocess.Popen(
                [os.path.abspath(script_url)],
                stdout=fout,
                stderr=fout,
            ) as process:
                process.wait()
                if process.returncode != 0:  # pragma: no cover
                    assert process.stderr
                    msg = process.stderr.read().decode()
                    raise CMBashSubmitError(f"Bad bash submit: {msg}")
    except Exception as msg:
        raise CMBashSubmitError(f"Bad bash submit: {msg}") from msg
    with open(stamp_url, "w", encoding="utf-8") as fstamp:
        fields = dict(status="accepted")
        yaml.dump(fields, fstamp)


def check_stamp_file(
    stamp_file: str | None,
    default_status: StatusEnum,
) -> StatusEnum:
    """Check a 'stamp' file for a status code

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
    if not os.path.exists(stamp_file):
        return default_status
    with open(stamp_file, encoding="utf-8") as fin:
        fields = yaml.safe_load(fin)
        return StatusEnum[fields["status"]]


def write_bash_script(
    script_url: str,
    command: str,
    **kwargs: Any,
) -> str:
    """Utility function to write a bash script for later execution

    Parameters
    ----------
    script_url: str
        Location to write the script

    command: str
        Main command line(s) in the script

    Keywords
    --------
    prepend: str | None
        Text to prepend before command

    append: str | None
        Test to append after command

    stamp: str | None
        Text to echo to stamp file when script completes

    stamp_url: str | None
        Stamp file to write to when script completes

    fake: str | None
        Echo command instead of running it

    rollback: str | None
        Prefix to script_url used when rolling back
        processing

    Returns
    -------
    script_url : str
        The path to the newly written script
    """
    prepend = kwargs.get("prepend")
    append = kwargs.get("append")
    fake = kwargs.get("fake")
    rollback_prefix = kwargs.get("rollback", "")

    script_url = f"{rollback_prefix}{script_url}"
    with contextlib.suppress(OSError):
        os.makedirs(os.path.dirname(script_url))

    with open(script_url, "w", encoding="utf-8") as fout:
        if prepend:
            fout.write(f"{prepend}\n")
        if fake:
            command = f"echo '{command}'"
        fout.write(command)
        fout.write("\n")
        if append:
            fout.write(f"{append}\n")
    return script_url
