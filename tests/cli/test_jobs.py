import os
import uuid

import pytest
from anyio import Path
from click.testing import CliRunner

from lsst.cmservice import models
from lsst.cmservice.cli.client import client_top
from lsst.cmservice.common.enums import DEFAULT_NAMESPACE, LevelEnum, StatusEnum

from .util_functions import (
    check_and_parse_result,
    check_get_methods,
    check_scripts,
    check_update_methods,
    create_tree,
)


@pytest.mark.asyncio()
async def test_job_cli(runner: CliRunner) -> None:
    """Test `job` CLI command"""

    # generate a uuid to avoid collisions
    namespace = uuid.uuid5(DEFAULT_NAMESPACE, str(uuid.uuid1()))

    os.environ["CM_CONFIGS"] = "examples"

    result = runner.invoke(client_top, "job list --output yaml")
    jobs = check_and_parse_result(result, list[models.Job])
    assert len(jobs) == 0, "Job list not empty"

    # intialize a tree down to one level lower
    create_tree(runner, client_top, LevelEnum.job, namespace)

    result = runner.invoke(client_top, "job list --output yaml")
    jobs = check_and_parse_result(result, list[models.Job])
    entry = jobs[0]

    # check get methods
    check_get_methods(runner, client_top, entry, "job", models.Job)

    # check update methods
    check_update_methods(runner, client_top, entry, "job", models.Job)

    # check scripts
    check_scripts(runner, client_top, entry, "job")

    # job specific stuff
    result = runner.invoke(client_top, f"job get parent --row_id {entry.id} --output yaml")
    parent = check_and_parse_result(result, models.ElementMixin)

    result = runner.invoke(client_top, f"job get errors --row_id {entry.id} --output yaml")
    job_errors = check_and_parse_result(result, list[models.PipetaskError])
    assert len(job_errors) == 0

    result = runner.invoke(
        client_top, f"job update status --status reviewable --row_id {entry.id} --output yaml"
    )
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.reviewable

    result = runner.invoke(client_top, f"job action reject --row_id {entry.id} --output yaml")
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.rejected

    result = runner.invoke(
        client_top, f"job update status --status rescuable --row_id {entry.id} --output yaml"
    )
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.rescuable

    result = runner.invoke(client_top, f"group action rescue_job --row_id {parent.id} --output yaml")
    rescue_job = check_and_parse_result(result, models.Job)
    assert rescue_job.attempt == 1

    result = runner.invoke(client_top, f"group get jobs --row_id {parent.id} --output yaml")
    jobs = check_and_parse_result(result, list[models.Job])
    assert len(jobs) == 2

    result = runner.invoke(
        client_top, f"job update status --status reviewable --row_id {rescue_job.id} --output yaml"
    )
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.reviewable

    result = runner.invoke(client_top, f"job action accept --row_id {rescue_job.id} --output yaml")
    check_accept = check_and_parse_result(result, models.Job)
    assert check_accept.status is StatusEnum.accepted

    result = runner.invoke(client_top, f"group action mark_rescued --row_id {parent.id} --output yaml")
    rescue_jobs = check_and_parse_result(result, list[models.Job])
    assert len(rescue_jobs) == 1

    result = runner.invoke(
        client_top, f"job update status --status rescuable --row_id {rescue_job.id} --output yaml"
    )
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.rescuable

    result = runner.invoke(client_top, f"action rescue-job --fullname {parent.fullname} --output yaml")
    rescue_job = check_and_parse_result(result, models.Job)

    result = runner.invoke(
        client_top, f"job update status --status accepted --row_id {rescue_job.id} --output yaml"
    )
    check_status = check_and_parse_result(result, dict)["status"]
    assert check_status is StatusEnum.accepted

    result = runner.invoke(client_top, f"action mark-job-rescued --fullname {parent.fullname} --output yaml")
    rescue_jobs = check_and_parse_result(result, list[models.Job])
    assert len(rescue_jobs) == 2

    result = runner.invoke(client_top, f"job action process --row_id {entry.id} --output yaml")
    check_changed = check_and_parse_result(result, dict)["changed"]
    assert not check_changed

    result = runner.invoke(client_top, f"action process --fullname {entry.fullname} --output yaml")
    check_changed = check_and_parse_result(result, dict)["changed"]
    assert not check_changed

    result = runner.invoke(client_top, f"job action run_check --row_id {entry.id} --output yaml")
    check_changed = check_and_parse_result(result, dict)["changed"]
    assert not check_changed

    fullpath = await Path("examples/manifest_report_2.yaml").resolve()
    result = runner.invoke(
        client_top, f"load manifest-report --fullname {entry.fullname} --yaml_file {fullpath}"
    )
    assert result.exit_code == 0
