import importlib
import sys
from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True, scope="function")
def import_deps() -> Generator:
    _ = importlib.import_module("lsst.cmservice.api.handlers.interface")
    _ = importlib.import_module("lsst.cmservice.api.handlers.jobs")
    _ = importlib.import_module("lsst.cmservice.api.handlers.functions")
    _ = importlib.import_module("lsst.cmservice.api.handlers.script_handler")
    yield
    del sys.modules["lsst.cmservice.api.handlers.interface"]
    del sys.modules["lsst.cmservice.api.handlers.jobs"]
    del sys.modules["lsst.cmservice.api.handlers.functions"]
    del sys.modules["lsst.cmservice.api.handlers.script_handler"]
