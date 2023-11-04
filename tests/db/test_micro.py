import pytest
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_micro(session: async_scoped_session) -> None:
    """Test fake end to end run using example/example_micro.yaml"""

    await interface.load_and_create_campaign(
        session,
        "examples/example_micro.yaml",
        "hsc_micro",
        "w_2023_41",
    )

    status = await interface.process(
        session,
        "hsc_micro/w_2023_41",
        fake_status=StatusEnum.accepted,
    )

    assert status == StatusEnum.accepted
