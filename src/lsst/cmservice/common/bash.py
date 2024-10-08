"""Utility functions for working with bash scripts"""

import contextlib
import os
import subprocess
from typing import Any

import yaml

from .enums import StatusEnum


def run_bash_job(
    script_url: str,
    log_url: str,
) -> None:
    """Run a bash job

    Parameters
    ----------
    script_url: str
        Script to submit

    log_url: str
        Location of log file to write
    """
    subprocess.run(["/bin/bash", script_url, ">", log_url], check=False)


def check_stamp_file(
    stamp_file: str,
) -> StatusEnum | None:
    """Check a 'stamp' file for a status code

    Parameters
    ----------
    stamp_file: str
        File to read for status

    Returns
    -------
    status: StatusEnum
        Status of the script
    """
    if not os.path.exists(stamp_file):
        return None
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
    stamp = kwargs.get("stamp")
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
        if stamp:
            stamp_url = kwargs["stamp_url"]
            fout.write(f'echo "status: {stamp}" > {os.path.abspath(stamp_url)}\n')
    return script_url
