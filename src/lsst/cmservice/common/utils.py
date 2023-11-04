from __future__ import annotations

import contextlib
import os
import sys
from collections.abc import Iterator


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
