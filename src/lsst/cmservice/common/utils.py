from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterator, Mapping
from typing import Any

import yaml


@contextlib.contextmanager
def add_sys_path(path: os.PathLike | str | None) -> Iterator[None]:
    """Temporarily add the given path to `sys.path`."""
    if path is None:
        yield
    else:
        path = os.fspath(path)
        try:
            sys.path.insert(0, path)
            yield
        finally:
            sys.path.remove(path)


def update_include_dict(
    orig_dict: dict[str, Any],
    include_dict: dict[str, Any],
) -> None:
    """Update a dict by updating (instead of replacing) sub-dicts

    Parameters
    ----------
    orig_dict: dict[str, Any]
        Original dict
    include_dict: dict[str, Any],
        Dict used to update the original
    """
    for key, val in include_dict.items():
        if isinstance(val, Mapping) and key in orig_dict:
            orig_dict[key].update(val)
        else:
            orig_dict[key] = val


# Synchronous file I/O utility functions included mostly to pass to
# `fastapi.concurrency.run_in_threadpool`


def yaml_safe_load(filename: str) -> dict:
    """Helper function to open yaml files using `yaml.safe_load`. To be used
    with `fastapi.concurrency.run_in_threadpool`

    Parameters
    ----------
    filename : `str`
        The path to the yaml file.

    Returns
    -------
    A dictionary returned by `yaml.safe_load`
    """
    with open(filename, encoding="utf-8") as file:
        return yaml.safe_load(file)


def yaml_dump(contents: str | dict | list, filename: str) -> None:
    """Helper function to open yaml files using `yaml.dump`. To be used
    with `fastapi.concurrency.run_in_threadpool`

    Parameters
    ----------
    contents: `str` | `Dict` | `list`
        The contents to be dumped in a yaml file.
    filename : `str`
        The path where the yaml file will be written.

    Returns
    -------
    A string, if the `dump` fails.
    """
    with open(filename, "w", encoding="utf-8") as fout:
        yaml.dump(contents, fout)


def read_lines(filename: str) -> list:
    """Helper function to open a file and return each line, string-by-string.
    Just here to wrap the `with` and pass function to
    `fastapi.concurrency.run_in_threadpool`

    Parameters
    ----------
    filename : `str`
        The path to the yaml file.

    Returns
    -------
    A list of full of the lines comprising the file, returned by standard
    python `readlines`.
    """
    with open(filename, encoding="utf-8") as fin:
        lines = fin.readlines()
        return lines
