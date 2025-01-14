import os
import sys
from typing import Any

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
from lsst.cmservice.common.utils import add_sys_path, update_include_dict


@pytest.mark.asyncio()
async def test_common_bash() -> None:
    """Test common.bash utilities"""

    the_script = await write_bash_script(
        "temp.sh",
        "ls",
        prepend="#!/usr/bin/env bash",
        append="# have a nice day",
        fake=True,
    )

    await run_bash_job(the_script, "temp.log", "temp.stamp")

    status = await check_stamp_file("temp.stamp", StatusEnum.running)
    assert status == StatusEnum.accepted

    status = await check_stamp_file("bad.stamp", StatusEnum.running)
    assert status == StatusEnum.running

    await Path("temp.sh").unlink(missing_ok=True)
    await Path("temp.stamp").unlink(missing_ok=True)
    await Path("temp.log").unlink(missing_ok=True)

    bps_dict = await parse_bps_stdout("examples/bps_stdout.log")
    assert bps_dict["run_id"].strip() == "334"

    diag_message = await get_diagnostic_message("examples/bps_stdout.log")
    assert diag_message == "dummy: ada"


def test_common_table_enums() -> None:
    """Test common.enums.TableEnum"""

    for table_val in range(TableEnum.production.value, TableEnum.script_template.value + 1):
        table_enum = TableEnum(table_val)

        if table_enum.is_node():
            assert table_enum.value in [1, 2, 3, 4, 5]

        if table_enum.is_element():
            assert table_enum.value in [1, 2, 3, 4]


def test_common_level_enums() -> None:
    """Test common.enums.LevelEnum"""
    assert LevelEnum.get_level_from_fullname("script:p0/c0/a_script") == LevelEnum.script
    assert LevelEnum.get_level_from_fullname("p0") == LevelEnum.production
    assert LevelEnum.get_level_from_fullname("p0/c0") == LevelEnum.campaign
    assert LevelEnum.get_level_from_fullname("p0/c0/s0") == LevelEnum.step
    assert LevelEnum.get_level_from_fullname("p0/c0/s0/g0") == LevelEnum.group
    assert LevelEnum.get_level_from_fullname("p0/c0/s0/g0/j0") == LevelEnum.job


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
        "htcondor_temp.sh",
        "htcondor_temp.log",
        "script_temp.sh",
        "script_temp.log",
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


def test_add_sys_path() -> None:
    """Test add_sys_path util"""
    with add_sys_path("examples"):
        assert "examples" in sys.path
    assert "examples" not in sys.path


def test_update_include_dict() -> None:
    """Test update_include_dict util"""
    orig_dict: dict[str, Any] = dict(
        alice="a",
        bob=dict(
            caleb="c",
            david="d",
        ),
    )
    include_dict: dict[str, Any] = dict(
        bob=dict(
            caleb="c",
            david="d",
            eric="e",
        ),
    )
    update_include_dict(orig_dict, include_dict)
    assert orig_dict["alice"] == "a"
    assert orig_dict["bob"]["eric"] == "e"
