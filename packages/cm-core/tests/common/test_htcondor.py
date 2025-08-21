# ruff: noqa
from typing import Any

from anyio import open_process, Path
from anyio.streams.file import FileReadStream
import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture()
async def htcondor_good_long_log() -> Any:
    """The output of a condor userlog command in -long format, delivered as
    a TextStream.

    This is an async fixture, so a consuming test must run inside an event loop
    by being marked with `@pytest.mark.asyncio`.
    """
    path = FIXTURES / "logs" / "bps_submit_good_long.condorlog"
    async with await FileReadStream.from_path(path) as stream:
        async for chunk in stream:
            yield chunk.decode()


@pytest.mark.asyncio
@pytest.mark.skip
async def test_check_htcondor(htcondor_good_long_log: Any) -> Any:
    async for line in htcondor_good_long_log:
        print(line)
