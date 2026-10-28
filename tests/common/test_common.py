import pytest
from anyio import Path

from lsst.cmservice.common.errors import (
    CMHTCondorSubmitError,
)
from lsst.cmservice.common.htcondor import check_htcondor_job, submit_htcondor_job, write_htcondor_script
from lsst.cmservice.models.enums import StatusEnum


def test_common_status_enums() -> None:
    """Test common.enums.StatusEnum"""

    for status_val in range(StatusEnum.failed.value, StatusEnum.rescued.value + 1):
        status_enum = StatusEnum(status_val)

        if status_enum.is_successful_element():
            assert status_enum.value >= StatusEnum.accepted.value

        if status_enum.is_successful_script():
            assert status_enum.value >= StatusEnum.reviewable.value

        if status_enum.is_bad():
            assert status_enum.value <= StatusEnum.rejected.value

        if status_enum.is_processable_element():
            assert (
                status_enum.value >= StatusEnum.waiting.value
                and status_enum.value <= StatusEnum.reviewable.value
            )

        if status_enum.is_processable_script():
            assert (
                status_enum.value >= StatusEnum.waiting.value
                and status_enum.value <= StatusEnum.reviewable.value
            )


# FIXME this test should patch the htcondor runner to produce an actual result
#       from a fixture.
@pytest.mark.asyncio()
async def test_common_htcondor() -> None:
    """Test common.htcondor functions"""

    _ht_condor_log = await write_htcondor_script(
        Path("htcondor_temp.sh"),
        Path("htcondor_temp.log"),
        Path("script_temp.sh"),
        Path("script_temp.log"),
    )

    with pytest.raises(CMHTCondorSubmitError):
        await submit_htcondor_job("htcondor_temp.sh")

    status = await check_htcondor_job("htcondor_temp.log")
    assert status is StatusEnum.failed

    await Path("htcondor_temp.sh").unlink()
