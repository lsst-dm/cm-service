from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterator, Mapping
from typing import Any


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
