from pathlib import Path
from typing import TypeAlias, TypeVar

from httpx import AsyncClient, Response
from pydantic import TypeAdapter

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.config import config

T = TypeVar("T")


def check_and_parse_response(
    response: Response,
    return_class: type[T],
) -> T:
    if not response.is_success:
        raise ValueError(f"{response.request} failed with {response.text}")
    return_obj = TypeAdapter(return_class).validate_python(response.json())
    return return_obj


def expect_failed_response(
    response: Response,
    expected_code: int = 500,
) -> None:
    if response.status_code != expected_code:
        raise ValueError(f"{response.request} did not fail as expected {response.status_code}")


async def add_scripts(
    client: AsyncClient,
    element: models.ElementMixin,
    api_version: str,
) -> tuple[list[models.Script], models.Dependency]:
    prep_script_model = models.ScriptCreate(
        name="prepare",
        parent_name=element.fullname,
        parent_level=element.level.value,  # type: ignore
        spec_block_name="null_script",
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/create",
        content=prep_script_model.model_dump_json(),
    )
    prep_script = check_and_parse_response(response, models.Script)

    collect_script_model = models.ScriptCreate(
        name="collect",
        parent_name=element.fullname,
        parent_level=element.level.value,  # type: ignore
        spec_block_name="null_script",
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/create",
        content=collect_script_model.model_dump_json(),
    )
    collect_script = check_and_parse_response(response, models.Script)

    script_depend_model = models.DependencyCreate(
        prereq_id=prep_script.id,
        depend_id=collect_script.id,
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script_dependency/create",
        content=script_depend_model.model_dump_json(),
    )
    script_depend = check_and_parse_response(response, models.Dependency)
    return ([prep_script, collect_script], script_depend)


async def create_tree(
    client: AsyncClient,
    api_version: str,
    level: LevelEnum,
    uuid_int: int,
) -> None:
    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"
    specification_load_model = models.SpecificationLoad(
        yaml_file=f"{fixtures}/empty_config.yaml",
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/load/specification",
        content=specification_load_model.model_dump_json(),
    )
    check_and_parse_response(response, models.Specification)

    pname = f"prod0_{uuid_int}"

    production_model = models.ProductionCreate(name=pname)
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/production/create",
        content=production_model.model_dump_json(),
    )
    check_and_parse_response(response, models.Production)

    cname = f"camp0_{uuid_int}"
    campaign_model = models.CampaignCreate(
        name=cname,
        spec_block_assoc_name="base#campaign",
        parent_name=pname,
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/campaign/create",
        content=campaign_model.model_dump_json(),
    )
    camp = check_and_parse_response(response, models.Campaign)

    (_camp_scripts, _camp_script_depend) = await add_scripts(client, camp, api_version)

    if level.value <= LevelEnum.campaign.value:
        return

    snames = [f"step{i}_{uuid_int}" for i in range(2)]
    steps = []
    for sname_ in snames:
        step_model = models.StepCreate(
            name=sname_,
            spec_block_name="basic_step",
            parent_name=camp.fullname,
        )
        response = await client.post(
            f"{config.asgi.prefix}/{api_version}/step/create",
            content=step_model.model_dump_json(),
        )
        step = check_and_parse_response(response, models.Step)
        steps.append(step)

    for step_ in steps:
        await add_scripts(client, step_, api_version)

    step_depend_model = models.DependencyCreate(
        prereq_id=steps[0].id,
        depend_id=steps[1].id,
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/step_dependency/create",
        content=step_depend_model.model_dump_json(),
    )
    step_depend = check_and_parse_response(response, models.Dependency)

    assert step_depend.prereq_id == steps[0].id
    assert step_depend.depend_id == steps[1].id
    # depend_is_done = await step_depend.is_done(session)
    # assert not depend_is_done

    if level.value <= LevelEnum.step.value:
        return

    gnames = [f"group{i}_{uuid_int}" for i in range(5)]
    groups = []
    for gname_ in gnames:
        group_model = models.GroupCreate(
            name=gname_,
            spec_block_name="group",
            parent_name=steps[1].fullname,
        )
        response = await client.post(
            f"{config.asgi.prefix}/{api_version}/group/create",
            content=group_model.model_dump_json(),
        )
        group = check_and_parse_response(response, models.Group)
        groups.append(group)

    for group_ in groups:
        await add_scripts(client, group_, api_version)

    if level.value <= LevelEnum.group.value:
        return

    jobs = []
    for group_ in groups:
        job_model = models.JobCreate(
            name=f"job_{uuid_int}",
            spec_block_name="job",
            parent_name=group_.fullname,
        )
        response = await client.post(
            f"{config.asgi.prefix}/{api_version}/job/create",
            content=job_model.model_dump_json(),
        )
        job = check_and_parse_response(response, models.Job)
        jobs.append(job)

    for job_ in jobs:
        await add_scripts(client, job_, api_version)

    return


async def delete_all_rows(
    client: AsyncClient,
    api_version: str,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/list")
    rows = check_and_parse_response(response, list[entry_class])

    for row_ in rows:
        await client.delete(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/delete/{row_.id}")

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/list")
    rows_check = check_and_parse_response(response, list[entry_class])

    assert len(rows_check) == 0, f"Failed to delete all {entry_class_name}"


async def delete_all_productions(
    client: AsyncClient,
    api_version: str,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_rows(client, api_version, "production", models.Production)
    if check_cascade:
        response = await client.get(f"{config.asgi.prefix}/{api_version}/campaign/list")
        n_campaigns = len(check_and_parse_response(response, list[models.Campaign]))
        assert n_campaigns == 0


async def delete_all_spec_stuff(
    client: AsyncClient,
    api_version: str,
) -> None:
    await delete_all_rows(client, api_version, "specification", models.Specification)
    await delete_all_rows(client, api_version, "spec_block", models.SpecBlock)


async def delete_all_queues(
    client: AsyncClient,
    api_version: str,
) -> None:
    await delete_all_rows(client, api_version, "queue", models.Queue)


async def cleanup(
    client: AsyncClient,
    api_version: str,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_productions(client, api_version, check_cascade=check_cascade)
    await delete_all_spec_stuff(client, api_version)
    await delete_all_queues(client, api_version)


async def check_update_methods(
    client: AsyncClient,
    api_version: str,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/data_dict",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.data["test"] == "dummy", "update_data_dict failed"

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/-1/data_dict",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/data_dict",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/data_dict",
    )
    expect_failed_response(response, 404)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/collections",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.collections["test"] == "dummy", "update_collections failed"

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/-1/collections",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/collections",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_collections failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/collections",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/resolved_collections",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_resolved_collections failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/resolved_collections",
    )
    expect_failed_response(response, 404)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/child_config",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.child_config["test"] == "dummy", "update_child_config failed"

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/-1/child_config",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/child_config",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_child_config failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/child_config",
    )
    expect_failed_response(response, 404)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/spec_aliases",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/-1/spec_aliases",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/spec_aliases",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_spec_aliases failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/spec_aliases",
    )
    expect_failed_response(response, 404)

    update_status_model = models.UpdateStatusQuery(
        fullname=entry.fullname,
        status=StatusEnum.reviewable,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/status",
        content=update_status_model.model_dump_json(),
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.reviewable

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/reject",
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.rejected, "reject() failed"

    reset_model = models.ResetQuery(
        fake_reset=True,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/reset",
        content=reset_model.model_dump_json(),
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.waiting, "reset() failed"

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/accept",
    )
    expect_failed_response(response, 500)

    update_status_model.status = StatusEnum.running
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/update/{entry.id}/status",
        content=update_status_model.model_dump_json(),
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.running

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/run_check",
    )
    check_run_check = check_and_parse_response(response, tuple[bool, StatusEnum])
    assert check_run_check[1] == StatusEnum.running

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/process",
    )
    check_process = check_and_parse_response(response, tuple[bool, StatusEnum])
    assert check_process[1] == StatusEnum.running

    process_query = models.ProcessNodeQuery(
        fullname=entry.fullname,
    )
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/actions/process",
        content=process_query.model_dump_json(),
    )
    check_process = check_and_parse_response(response, tuple[bool, StatusEnum])
    assert check_process[1] == StatusEnum.running

    process_query.fake_status = StatusEnum.running.value
    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/actions/process",
        content=process_query.model_dump_json(),
    )
    check_process = check_and_parse_response(response, tuple[bool, StatusEnum])
    assert check_process[1] == StatusEnum.running

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/accept",
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.accepted

    response = await client.delete(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/delete/{entry.id}",
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/reject",
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/reset",
        content=reset_model.model_dump_json(),
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/accept",
    )
    expect_failed_response(response, 404)

    response = await client.delete(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/delete/-1",
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/reject",
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/reset",
        content=reset_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/process",
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/run_check",
    )
    expect_failed_response(response, 404)


async def check_scripts(
    client: AsyncClient,
    api_version: str,
    entry: models.ElementMixin,
    entry_class_name: str,
) -> None:
    query_model = models.ScriptQuery(
        fullname=entry.fullname,
        script_name=None,
    )
    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/scripts",
        params=query_model.model_dump(),
    )
    scripts = check_and_parse_response(response, list[models.Script])
    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    for script_ in scripts:
        response = await client.get(
            f"{config.asgi.prefix}/{api_version}/script/get/{script_.id}/parent",
        )
        parent_check = check_and_parse_response(response, models.ElementMixin)
        assert parent_check.id == entry.id

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/-1/parent",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/scripts",
        params=query_model.model_dump(),
    )
    expect_failed_response(response, 404)

    query_model = models.ScriptQuery(
        fullname=entry.fullname,
        script_name="bad",
    )
    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/scripts",
        params=query_model.model_dump(),
    )

    no_scripts = check_and_parse_response(response, list[models.Script])
    assert len(no_scripts) == 0, "get_scripts with bad script_name did not return []"

    query_model1 = models.ScriptQuery(
        fullname=entry.fullname,
        script_name=None,
    )
    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/all_scripts",
        params=query_model1.model_dump(),
    )
    all_scripts = check_and_parse_response(response, list[models.Script])
    assert len(all_scripts) != 0, "get_all_scripts with failed"

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/all_scripts",
        params=query_model1.model_dump(),
    )
    expect_failed_response(response, 404)

    script0 = scripts[0]
    script1 = scripts[1]

    if script0.id > script1.id:
        script0 = scripts[1]
        script1 = scripts[0]

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/{script0.id}/check_prerequisites",
    )
    script0_prereq = check_and_parse_response(response, bool)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/{script1.id}/check_prerequisites",
    )
    script1_prereq = check_and_parse_response(response, bool)
    assert script0_prereq
    assert not script1_prereq

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/-1/check_prerequisites",
    )
    expect_failed_response(response, 404)

    update_status_model = models.UpdateStatusQuery(
        fullname=entry.fullname,
        status=StatusEnum.failed,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/update/{script0.id}/status",
        content=update_status_model.model_dump_json(),
    )
    update_check = check_and_parse_response(response, models.Script)
    assert update_check.status == StatusEnum.failed

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/update/-1/status",
        content=update_status_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    query_model2 = models.RetryScriptQuery(
        fullname=entry.fullname,
        script_name="prepare",
        fake_reset=True,
        status=StatusEnum.waiting,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/{entry.id}/retry_script",
        content=query_model2.model_dump_json(),
    )
    retry_check = check_and_parse_response(response, models.Script)
    assert retry_check.status == StatusEnum.waiting

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/action/-1/retry_script",
        content=query_model2.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/update/{script0.id}/status",
        content=update_status_model.model_dump_json(),
    )
    update_check = check_and_parse_response(response, models.Script)
    assert update_check.status == StatusEnum.failed

    reset_query = models.ResetQuery(
        status=StatusEnum.waiting,
        fake_reset=True,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/action/{script0.id}/reset_script",
        content=reset_query.model_dump_json(),
    )
    status_check = check_and_parse_response(response, StatusEnum)
    assert status_check == StatusEnum.waiting

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/update/{script0.id}/status",
        content=update_status_model.model_dump_json(),
    )
    update_check = check_and_parse_response(response, models.Script)
    assert update_check.status == StatusEnum.failed

    script_reset_status_model = models.ResetScriptQuery(
        fullname=script0.fullname,
        status=StatusEnum.waiting,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/actions/reset_script",
        content=script_reset_status_model.model_dump_json(),
    )
    reset_check = check_and_parse_response(response, models.Script)
    assert reset_check.status == StatusEnum.waiting

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/script/action/-1/reset_script",
        content=update_status_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/{script0.id}/script_errors",
    )
    check_errors = check_and_parse_response(response, list[models.ScriptError])
    assert len(check_errors) == 1

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/script/get/-1/script_errors",
    )
    expect_failed_response(response, 404)


async def check_get_methods(
    client: AsyncClient,
    api_version: str,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}",
    )
    check_get = check_and_parse_response(response, entry_class)

    assert check_get.id == entry.id, "pulled row should be identical"
    assert check_get.level == entry.level, "pulled row db_id should be identical"  # type: ignore

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1")
    expect_failed_response(response, 404)

    get_fullname_model = models.FullnameQuery(
        fullname=entry.fullname,
    )
    bad_fullname_model = models.FullnameQuery(fullname="bad/bad")

    get_name_model = models.NameQuery(
        name=entry.name,
    )
    bad_name_model = models.NameQuery(name="bad")

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get_row_by_fullname",
        params=get_fullname_model.model_dump(),
    )
    check_other = check_and_parse_response(response, entry_class)
    assert check_get.id == check_other.id

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get_row_by_fullname",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get_row_by_name",
        params=get_name_model.model_dump(),
    )
    check_other = check_and_parse_response(response, entry_class)
    assert check_get.id == check_other.id

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get_row_by_name",
        params=bad_name_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/spec_block"
    )
    spec_block_check = check_and_parse_response(response, models.SpecBlock)
    assert spec_block_check.name

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/spec_block")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/specification",
    )
    specification_check = check_and_parse_response(response, models.Specification)
    assert specification_check.name

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/specification")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/tasks",
    )
    check1 = check_and_parse_response(response, models.MergedTaskSetDict)
    assert len(check1.reports) == 0, "length of tasks should be 0"

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/tasks")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/wms_task_reports",
    )
    check2 = check_and_parse_response(response, models.MergedWmsTaskReportDict)

    assert len(check2.reports) == 0, "length of reports should be 0"
    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/wms_task_reports"
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/{entry.id}/products",
    )
    check3 = check_and_parse_response(response, models.MergedProductSetDict)
    assert len(check3.reports) == 0, "length of products should be 0"

    response = await client.get(f"{config.asgi.prefix}/{api_version}/{entry_class_name}/get/-1/products")
    expect_failed_response(response, 404)

    expect_failed_response(response, 404)


async def check_queue(
    client: AsyncClient,
    api_version: str,
    entry: models.ElementMixin,
) -> None:
    # make and test a queue object

    fullname_model = models.FullnameQuery(
        fullname=entry.fullname,
    )

    response = await client.post(
        f"{config.asgi.prefix}/{api_version}/queue/create",
        content=fullname_model.model_dump_json(),
    )
    queue = check_and_parse_response(response, models.Queue)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/queue/sleep_time/{queue.id}",
    )
    sleep_time = check_and_parse_response(response, int)
    assert sleep_time == 10

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/queue/sleep_time/-1",
    )

    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/queue/process/{queue.id}",
    )
    changed = check_and_parse_response(response, bool)
    assert not changed

    response = await client.get(
        f"{config.asgi.prefix}/{api_version}/queue/process/-1",
    )
    expect_failed_response(response, 404)
