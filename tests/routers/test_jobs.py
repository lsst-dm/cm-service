import os
import uuid

import pytest
from httpx import AsyncClient

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
    check_get_methods,
    check_queue,
    check_scripts,
    check_update_methods,
    cleanup,
    create_tree,
    expect_failed_response,
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_job_routes(client: AsyncClient) -> None:
    """Test `/job` API endpoint."""

    # generate a uuid to avoid collisions
    uuid_int = uuid.uuid1().int

    os.environ["CM_CONFIGS"] = "examples"

    # intialize a tree down to one level lower
    await create_tree(client, LevelEnum.job, uuid_int)

    response = await client.get(f"{config.prefix}/job/list")
    jobs = check_and_parse_response(response, list[models.Job])
    entry = jobs[0]

    # check get methods
    await check_get_methods(client, entry, "job", models.Job, models.Group)

    # check update methods
    await check_update_methods(client, entry, "job", models.Job)

    # check scripts
    await check_scripts(client, entry, "job")

    # check queues
    await check_queue(client, entry)

    # test some job-specific stuff
    response = await client.get(
        f"{config.prefix}/job/get/{entry.id}/parent",
    )
    parent = check_and_parse_response(response, models.Group)

    response = await client.get(
        f"{config.prefix}/job/get/{entry.id}/errors",
    )
    check_errors = check_and_parse_response(response, list[models.PipetaskError])
    assert len(check_errors) == 0

    response = await client.get(
        f"{config.prefix}/job/get/-1/errors",
    )
    expect_failed_response(response, 404)

    update_model = models.JobUpdate(
        fullname=entry.fullname,
        status=StatusEnum.rescuable,
    )
    response = await client.put(
        f"{config.prefix}/job/update/{entry.id}",
        content=update_model.model_dump_json(),
    )

    response = await client.put(
        f"{config.prefix}/job/update/-1",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.prefix}/group/action/{parent.id}/rescue_job",
    )
    rescue_job = check_and_parse_response(response, models.Job)
    assert rescue_job.attempt == 1

    response = await client.put(
        f"{config.prefix}/job/update/{rescue_job.id}",
        content=update_model.model_dump_json(),
    )

    rescue_node_model = models.NodeQuery(fullname=parent.fullname)

    response = await client.post(
        f"{config.prefix}/actions/rescue_job", content=rescue_node_model.model_dump_json()
    )
    rescue_job = check_and_parse_response(response, models.Job)
    assert rescue_job.attempt == 2

    response = await client.get(
        f"{config.prefix}/group/get/{parent.id}/jobs",
    )
    check_jobs = check_and_parse_response(response, list[models.Job])
    assert len(check_jobs) == 3
    new_job = check_jobs[-1]

    response = await client.get(
        f"{config.prefix}/group/get/-1/jobs",
    )
    expect_failed_response(response, 404)

    update_model.status = StatusEnum.accepted
    response = await client.put(
        f"{config.prefix}/job/update/{new_job.id}",
        content=update_model.model_dump_json(),
    )

    response = await client.post(
        f"{config.prefix}/group/action/{parent.id}/mark_rescued",
    )
    check_jobs = check_and_parse_response(response, list[models.Job])
    assert len(check_jobs) == 2

    # delete everything we just made in the session
    await cleanup(client, check_cascade=True)
