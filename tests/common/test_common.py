import os
import sys
from typing import Any

import pytest

from lsst.cmservice.common import bash, enums, errors, htcondor, slurm, utils


@pytest.mark.asyncio()
async def test_common_bash() -> None:
    """Test common.bash utilities"""

    the_script = bash.write_bash_script(
        "temp.sh",
        "ls",
        prepend="#!/usr/bin/env bash",
        append="# have a nice day",
        fake=True,
    )

    bash.run_bash_job(the_script, "temp.log", "temp.stamp")

    status = bash.check_stamp_file("temp.stamp", enums.StatusEnum.running)
    assert status == enums.StatusEnum.accepted

    status = bash.check_stamp_file("bad.stamp", enums.StatusEnum.running)
    assert status == enums.StatusEnum.running

    os.unlink("temp.sh")
    os.unlink("temp.stamp")

    if os.path.exists("temp.log"):
        os.unlink("temp.log")

    bps_dict = bash.parse_bps_stdout("examples/bps_stdout.log")
    assert bps_dict["run_id"].strip() == "334"

    diag_message = await bash.get_diagnostic_message("examples/bps_stdout.log")
    assert diag_message == "dummy: ada"


def test_common_table_enums() -> None:
    """Test common.enums.TableEnum"""

    for table_val in range(enums.TableEnum.production.value, enums.TableEnum.script_template.value + 1):
        table_enum = enums.TableEnum(table_val)

        if table_enum.is_node():
            assert table_enum.value in [1, 2, 3, 4, 5]

        if table_enum.is_element():
            assert table_enum.value in [1, 2, 3, 4]


def test_common_level_enums() -> None:
    """Test common.enums.LevelEnum"""
    assert enums.LevelEnum.get_level_from_fullname("script:p0/c0/a_script") == enums.LevelEnum.script
    assert enums.LevelEnum.get_level_from_fullname("p0") == enums.LevelEnum.production
    assert enums.LevelEnum.get_level_from_fullname("p0/c0") == enums.LevelEnum.campaign
    assert enums.LevelEnum.get_level_from_fullname("p0/c0/s0") == enums.LevelEnum.step
    assert enums.LevelEnum.get_level_from_fullname("p0/c0/s0/g0") == enums.LevelEnum.group
    assert enums.LevelEnum.get_level_from_fullname("p0/c0/s0/g0/j0") == enums.LevelEnum.job


def test_common_status_enums() -> None:
    """Test common.enums.StatusEnum"""

    for status_val in range(enums.StatusEnum.failed.value, enums.StatusEnum.rescued.value + 1):
        status_enum = enums.StatusEnum(status_val)

        if status_enum.is_successful_element():
            assert status_enum.value >= enums.StatusEnum.accepted.value

        if status_enum.is_successful_script():
            assert status_enum.value >= enums.StatusEnum.reviewable.value

        if status_enum.is_bad():
            assert status_enum.value <= enums.StatusEnum.rejected.value

        if status_enum.is_processable_element():
            assert (
                status_enum.value >= enums.StatusEnum.waiting.value
                and status_enum.value <= enums.StatusEnum.reviewable.value
            )

        if status_enum.is_processable_script():
            assert (
                status_enum.value >= enums.StatusEnum.waiting.value
                and status_enum.value <= enums.StatusEnum.reviewable.value
            )


def test_common_htcondor() -> None:
    """Test common.htcondor functions"""

    _ht_condor_log = htcondor.write_htcondor_script(
        "htcondor_temp.sh",
        "htcondor_temp.log",
        "script_temp.sh",
        "script_temp.log",
    )

    with pytest.raises(errors.CMHTCondorSubmitError):
        htcondor.submit_htcondor_job("htcondor_temp.sh")

    with pytest.raises(errors.CMHTCondorCheckError):
        htcondor.check_htcondor_job("htcondor_temp.log")

    os.unlink("htcondor_temp.sh")


def test_common_slurm() -> None:
    """Test common.slurm functions"""

    with pytest.raises(errors.CMSlurmSubmitError):
        slurm.submit_slurm_job("slurm_temp.sh", "slurm_temp.log")

    with pytest.raises(errors.CMSlurmCheckError):
        slurm.check_slurm_job("slurm_temp.log")


def test_add_sys_path() -> None:
    """Test add_sys_path util"""
    with utils.add_sys_path("examples"):
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
    utils.update_include_dict(orig_dict, include_dict)
    assert orig_dict["alice"] == "a"
    assert orig_dict["bob"]["eric"] == "e"
