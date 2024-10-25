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
) -> tuple[list[models.Script], models.Dependency]:
    prep_script_model = models.ScriptCreate(
        name="prepare",
        parent_name=element.fullname,
        parent_level=element.level.value,
        spec_block_name="null_script",
    )

    response = await client.post(
        f"{config.prefix}/script/create",
        content=prep_script_model.model_dump_json(),
    )
    prep_script = check_and_parse_response(response, models.Script)

    collect_script_model = models.ScriptCreate(
        name="collect",
        parent_name=element.fullname,
        parent_level=element.level.value,
        spec_block_name="null_script",
    )
    response = await client.post(
        f"{config.prefix}/script/create",
        content=collect_script_model.model_dump_json(),
    )
    collect_script = check_and_parse_response(response, models.Script)

    script_depend_model = models.DependencyCreate(
        prereq_id=prep_script.id,
        depend_id=collect_script.id,
    )
    response = await client.post(
        f"{config.prefix}/script_dependency/create",
        content=script_depend_model.model_dump_json(),
    )
    script_depend = check_and_parse_response(response, models.Dependency)
    return ([prep_script, collect_script], script_depend)


async def create_tree(
    client: AsyncClient,
    level: LevelEnum,
    uuid_int: int,
) -> None:
    specification_load_model = models.SpecificationLoad(
        yaml_file="examples/empty_config.yaml",
    )
    response = await client.post(
        f"{config.prefix}/load/specification",
        content=specification_load_model.model_dump_json(),
    )
    check_and_parse_response(response, models.Specification)

    pname = f"prod0_{uuid_int}"

    production_model = models.ProductionCreate(name=pname)
    response = await client.post(
        f"{config.prefix}/production/create",
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
        f"{config.prefix}/campaign/create",
        content=campaign_model.model_dump_json(),
    )
    camp = check_and_parse_response(response, models.Campaign)

    (camp_scripts, camp_script_depend) = await add_scripts(client, camp)

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
            f"{config.prefix}/step/create",
            content=step_model.model_dump_json(),
        )
        step = check_and_parse_response(response, models.Step)
        steps.append(step)

    for step_ in steps:
        await add_scripts(client, step_)

    step_depend_model = models.DependencyCreate(
        prereq_id=steps[0].id,
        depend_id=steps[1].id,
    )
    response = await client.post(
        f"{config.prefix}/step_dependency/create",
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
            f"{config.prefix}/group/create",
            content=group_model.model_dump_json(),
        )
        group = check_and_parse_response(response, models.Group)
        groups.append(group)

    for group_ in groups:
        await add_scripts(client, group_)

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
            f"{config.prefix}/job/create",
            content=job_model.model_dump_json(),
        )
        job = check_and_parse_response(response, models.Job)
        jobs.append(job)

    for job_ in jobs:
        await add_scripts(client, job_)

    return


async def delete_all_rows(
    client: AsyncClient,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    response = await client.get(f"{config.prefix}/{entry_class_name}/list")
    rows = check_and_parse_response(response, list[entry_class])

    for row_ in rows:
        await client.delete(f"{config.prefix}/{entry_class_name}/delete/{row_.id}")

    response = await client.get(f"{config.prefix}/{entry_class_name}/list")
    rows_check = check_and_parse_response(response, list[entry_class])

    assert len(rows_check) == 0, f"Failed to delete all {entry_class_name}"


async def delete_all_productions(
    client: AsyncClient,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_rows(client, "production", models.Production)
    if check_cascade:
        response = await client.get(f"{config.prefix}/campaign/list")
        n_campaigns = len(check_and_parse_response(response, list[models.Campaign]))
        assert n_campaigns == 0


async def delete_all_spec_stuff(
    client: AsyncClient,
) -> None:
    await delete_all_rows(client, "specification", models.Specification)
    await delete_all_rows(client, "spec_block", models.SpecBlock)
    await delete_all_rows(client, "script_template", models.ScriptTemplate)


async def delete_all_queues(
    client: AsyncClient,
) -> None:
    await delete_all_rows(client, "queue", models.Queue)


async def cleanup(
    client: AsyncClient,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_productions(client, check_cascade=check_cascade)
    await delete_all_spec_stuff(client)
    await delete_all_queues(client)


async def check_update_methods(
    client: AsyncClient,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/data_dict",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.data["test"] == "dummy", "update_data_dict failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/-1/data_dict",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/data_dict",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/-1/data_dict",
    )
    expect_failed_response(response, 404)

    get_fullname_model = models.FullnameQuery(
        fullname=entry.fullname,
    )
    bad_fullname_model = models.FullnameQuery(
        fullname="bad/bad",
    )
    invalid_fullname_model = models.FullnameQuery(fullname="invalid")

    response = await client.get(
        f"{config.prefix}/get/data_dict",
        params=get_fullname_model.model_dump(),
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    response = await client.get(
        f"{config.prefix}/get/data_dict",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/data_dict",
        params=invalid_fullname_model.model_dump(),
    )
    expect_failed_response(response, 500)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/collections",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.collections["test"] == "dummy", "update_collections failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/-1/collections",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/collections",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_collections failed"

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/-1/collections",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/collections",
        params=get_fullname_model.model_dump(),
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_collections failed"

    response = await client.get(
        f"{config.prefix}/get/collections",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/collections",
        params=invalid_fullname_model.model_dump(),
    )
    expect_failed_response(response, 500)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/resolved_collections",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_resolved_collections failed"

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/-1/resolved_collections",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/resolved_collections",
        params=get_fullname_model.model_dump(),
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_resolved_collections failed"

    response = await client.get(
        f"{config.prefix}/get/resolved_collections",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/collections",
        params=invalid_fullname_model.model_dump(),
    )
    expect_failed_response(response, 500)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/child_config",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.child_config["test"] == "dummy", "update_child_config failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/-1/child_config",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/child_config",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_child_config failed"

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/-1/child_config",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/child_config",
        params=get_fullname_model.model_dump(),
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_child_config failed"

    response = await client.get(
        f"{config.prefix}/get/child_config",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/child_config",
        params=invalid_fullname_model.model_dump(),
    )
    expect_failed_response(response, 500)

    update_model = models.UpdateNodeQuery(
        fullname=entry.fullname,
        update_dict=dict(test="dummy"),
    )
    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/spec_aliases",
        content=update_model.model_dump_json(),
    )
    check = check_and_parse_response(response, entry_class)
    assert check.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/-1/spec_aliases",
        content=update_model.model_dump_json(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/spec_aliases",
    )
    check = check_and_parse_response(response, dict)
    assert check["test"] == "dummy", "get_spec_aliases failed"

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/-1/spec_aliases",
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/spec_aliases",
        params=get_fullname_model.model_dump(),
    )
    check = check_and_parse_response(response, dict)

    assert check["test"] == "dummy", "get_spec_aliases failed"

    response = await client.get(
        f"{config.prefix}/get/spec_aliases",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/spec_aliases",
        params=invalid_fullname_model.model_dump(),
    )
    expect_failed_response(response, 500)
    update_status_model = models.UpdateStatusQuery(
        fullname=entry.fullname,
        status=StatusEnum.reviewable,
    )

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/status",
        content=update_status_model.model_dump_json(),
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.reviewable

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/reject",
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.rejected, "reject() failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/reset",
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.waiting, "reset() failed"

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/accept",
    )
    expect_failed_response(response, 500)

    update_status_model.status = StatusEnum.running
    response = await client.post(
        f"{config.prefix}/{entry_class_name}/update/{entry.id}/status",
        content=update_status_model.model_dump_json(),
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.running

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/accept",
    )
    check_update = check_and_parse_response(response, entry_class)
    assert check_update.status == StatusEnum.accepted

    response = await client.delete(
        f"{config.prefix}/{entry_class_name}/delete/{entry.id}",
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/reject",
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/{entry.id}/reset",
    )
    expect_failed_response(response, 500)

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/-1/accept",
    )
    expect_failed_response(response, 404)

    response = await client.delete(
        f"{config.prefix}/{entry_class_name}/delete/-1",
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/-1/reject",
    )
    expect_failed_response(response, 404)

    response = await client.post(
        f"{config.prefix}/{entry_class_name}/action/-1/reset",
    )
    expect_failed_response(response, 404)


async def check_scripts(
    client: AsyncClient,
    entry: models.ElementMixin,
    entry_class_name: str,
) -> None:
    query_model = models.ScriptQuery(
        fullname=entry.fullname,
        script_name=None,
    )
    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/scripts",
        params=query_model.model_dump(),
    )
    scripts = check_and_parse_response(response, list[models.Script])
    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    query_model = models.ScriptQuery(
        fullname=entry.fullname,
        script_name="bad",
    )
    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/scripts",
        params=query_model.model_dump(),
    )

    no_scripts = check_and_parse_response(response, list[models.Script])
    assert len(no_scripts) == 0, "get_scripts with bad script_name did not return []"

    query_model = models.ScriptQuery(
        fullname=entry.fullname,
        script_name=None,
    )
    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/all_scripts",
        params=query_model.model_dump(),
    )
    all_scripts = check_and_parse_response(response, list[models.Script])
    assert len(all_scripts) != 0, "get_all_scripts with failed"


async def check_get_methods(
    client: AsyncClient,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
    parent_class: TypeAlias = models.ElementMixin,
) -> None:
    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}",
    )
    check_get = check_and_parse_response(response, entry_class)

    assert check_get.id == entry.id, "pulled row should be identical"
    assert check_get.level == entry.level, "pulled row db_id should be identical"

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1")
    expect_failed_response(response, 404)

    get_fullname_model = models.FullnameQuery(
        fullname=entry.fullname,
    )
    bad_fullname_model = models.FullnameQuery(fullname="bad/bad")
    models.FullnameQuery(fullname="invalid")
    get_name_model = models.NameQuery(
        name=entry.name,
    )
    bad_name_model = models.NameQuery(name="bad")

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get_row_by_fullname",
        params=get_fullname_model.model_dump(),
    )
    check_other = check_and_parse_response(response, entry_class)
    assert check_get.id == check_other.id

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get_row_by_fullname",
        params=bad_fullname_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get_row_by_name",
        params=get_name_model.model_dump(),
    )
    check_other = check_and_parse_response(response, entry_class)
    assert check_get.id == check_other.id

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get_row_by_name",
        params=bad_name_model.model_dump(),
    )
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/spec_block",
        params=get_fullname_model.model_dump(),
    )
    spec_block = check_and_parse_response(response, models.SpecBlock)

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/{entry.id}/spec_block")
    spec_block_check = check_and_parse_response(response, models.SpecBlock)
    assert spec_block.name == spec_block_check.name

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1/spec_block")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/get/specification",
        params=get_fullname_model.model_dump(),
    )
    specification = check_and_parse_response(response, models.Specification)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/specification",
    )
    specification_check = check_and_parse_response(response, models.Specification)
    assert specification.name == specification_check.name

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1/specification")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/tasks",
    )
    check = check_and_parse_response(response, models.MergedTaskSetDict)
    assert len(check.reports) == 0, "length of tasks should be 0"

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1/tasks")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/wms_task_reports",
    )
    check = check_and_parse_response(response, models.MergedWmsTaskReportDict)

    assert len(check.reports) == 0, "length of reports should be 0"
    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1/wms_task_reports")
    expect_failed_response(response, 404)

    response = await client.get(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/products",
    )
    check = check_and_parse_response(response, models.MergedProductSetDict)
    assert len(check.reports) == 0, "length of products should be 0"

    response = await client.get(f"{config.prefix}/{entry_class_name}/get/-1/products")
    expect_failed_response(response, 404)


async def check_queue(
    client: AsyncClient,
    entry: models.ElementMixin,
) -> None:
    # TODO, make and test queue object
    pass
