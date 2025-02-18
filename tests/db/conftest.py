import importlib
import sys
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True, scope="function")
def import_deps() -> Generator:
    _ = importlib.import_module("lsst.cmservice.handlers.interface")
    _ = importlib.import_module("lsst.cmservice.handlers.jobs")
    _ = importlib.import_module("lsst.cmservice.handlers.functions")
    _ = importlib.import_module("lsst.cmservice.handlers.script_handler")
    yield
    del sys.modules["lsst.cmservice.handlers.interface"]
    del sys.modules["lsst.cmservice.handlers.jobs"]
    del sys.modules["lsst.cmservice.handlers.functions"]
    del sys.modules["lsst.cmservice.handlers.script_handler"]
