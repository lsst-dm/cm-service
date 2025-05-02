import os

import pytest
from anyio import Path

from lsst.cmservice.common.bash import (
    check_stamp_file,
    get_diagnostic_message,
    parse_bps_stdout,
    run_bash_job,
    write_bash_script,
)
from lsst.cmservice.common.enums import LevelEnum, StatusEnum, TableEnum
from lsst.cmservice.common.errors import (
    CMHTCondorCheckError,
    CMHTCondorSubmitError,
    CMSlurmCheckError,
    CMSlurmSubmitError,
)
from lsst.cmservice.common.htcondor import check_htcondor_job, submit_htcondor_job, write_htcondor_script
from lsst.cmservice.common.slurm import check_slurm_job, submit_slurm_job


@pytest.mark.asyncio()
async def test_common_bash() -> None:
    """Test common.bash utilities"""

    fixtures = Path(__file__).parent.parent / "fixtures" / "logs"
    the_script = await write_bash_script(
        "temp.sh",
        "ls",
        fake=True,
        values=dict(append="# have a nice day", script_method="bash"),
    )

    await run_bash_job(the_script, "temp.log", "temp.stamp")

    status = await check_stamp_file("temp.stamp", StatusEnum.running)
    assert status == StatusEnum.accepted

    status = await check_stamp_file("bad.stamp", StatusEnum.running)
    assert status == StatusEnum.running

    await Path("temp.sh").unlink(missing_ok=True)
    await Path("temp.stamp").unlink(missing_ok=True)
    await Path("temp.log").unlink(missing_ok=True)

    bps_dict = await parse_bps_stdout(f"{fixtures}/bps_stdout.log")
    assert bps_dict["Run Id"] == "12345678.0"

    diag_message = await get_diagnostic_message(f"{fixtures}/bps_stdout.log")
    assert diag_message == "dummy: ada"


def test_common_table_enums() -> None:
    """Test common.enums.TableEnum"""

    for table_val in TableEnum:
        table_enum = TableEnum(table_val)

        if table_enum.is_node():
            assert table_enum.value in [1, 2, 3, 4, 5]

        if table_enum.is_element():
            assert table_enum.value in [1, 2, 3, 4]


def test_common_level_enums() -> None:
    """Test common.enums.LevelEnum"""
    assert LevelEnum.get_level_from_fullname("script:c0/a_script") == LevelEnum.script
    assert LevelEnum.get_level_from_fullname("c0") == LevelEnum.campaign
    assert LevelEnum.get_level_from_fullname("c0/s0") == LevelEnum.step
    assert LevelEnum.get_level_from_fullname("c0/s0/g0") == LevelEnum.group
    assert LevelEnum.get_level_from_fullname("c0/s0/g0/j0") == LevelEnum.job


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

    with pytest.raises(CMHTCondorCheckError):
        await check_htcondor_job("htcondor_temp.log")

    os.unlink("htcondor_temp.sh")


# FIXME this test should patch the htcondor runner to produce an actual result
#       from a fixture.
@pytest.mark.asyncio()
async def test_common_slurm() -> None:
    """Test common.slurm functions"""

    with pytest.raises(CMSlurmSubmitError):
        await submit_slurm_job("slurm_temp.sh", "slurm_temp.log")

    with pytest.raises(CMSlurmCheckError):
        await check_slurm_job("slurm_temp.log")
