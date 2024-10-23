from typing import TypeAlias, TypeVar

import yaml
from click import BaseCommand
from click.testing import CliRunner, Result
from pydantic import parse_obj_as

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum

T = TypeVar("T")


def check_and_parse_result(
    result: Result,
    return_class: type[T],
) -> T:
    if not result.exit_code == 0:
        raise ValueError(f"{result} failed with {result.exit_code} {result.output}")
    return_obj = parse_obj_as(return_class, yaml.unsafe_load(result.stdout))
    return return_obj


def expect_failed_result(
    result: Result,
    expected_code: int = 1,
) -> None:
    if result.exit_code != expected_code:
        raise ValueError(f"{result} did not fail as expected {result.exit_code}")


def add_scripts(
    runner: CliRunner,
    client_top: BaseCommand,
    element: models.ElementMixin,
) -> tuple[list[models.Script], models.Dependency]:
    result = runner.invoke(
        client_top,
        "script create "
        "--output yaml "
        "--name prepare "
        f"--parent_name {element.fullname} "
        "--spec_block_name null_script",
    )
    prep_script = check_and_parse_result(result, models.Script)

    result = runner.invoke(
        client_top,
        "script create "
        "--output yaml "
        "--name collect "
        f"--parent_name {element.fullname} "
        "--spec_block_name null_script",
    )
    collect_script = check_and_parse_result(result, models.Script)

    result = runner.invoke(
        client_top,
        "script_dependency create ",
        "--output yaml " f"--prereq_id {prep_script.id} " f"--depend_id {collect_script.id} ",
    )
    # script_depend = check_and_parse_result(result, models.Dependency)
    script_depend = None
    return ([prep_script, collect_script], script_depend)


def create_tree(
    runner: CliRunner,
    client_top: BaseCommand,
    level: LevelEnum,
    uuid_int: int,
) -> None:
    result = runner.invoke(
        client_top,
        "load specification " "--output yaml " "--yaml_file examples/empty_config.yaml",
    )
    # check_and_parse_result(result, models.Specification)

    pname = f"prod0_{uuid_int}"

    result = runner.invoke(client_top, "production create " "--output yaml " f"--name {pname}")
    check_and_parse_result(result, models.Production)

    cname = f"camp0_{uuid_int}"
    result = runner.invoke(
        client_top,
        "campaign create "
        "--output yaml "
        f"--name {cname} "
        "--spec_block_assoc_name base#campaign "
        f"--parent_name {pname}",
    )
    camp = check_and_parse_result(result, models.Campaign)

    (camp_scripts, camp_script_depend) = add_scripts(runner, client_top, camp)

    if level.value <= LevelEnum.campaign.value:
        return

    snames = [f"step{i}_{uuid_int}" for i in range(2)]
    steps = []
    for sname_ in snames:
        result = runner.invoke(
            client_top,
            "step create "
            "--output yaml "
            f"--name {sname_} "
            "--spec_block_name basic_step "
            f"--parent_name {camp.fullname}",
        )
        step = check_and_parse_result(result, models.Step)
        steps.append(step)

    for step_ in steps:
        add_scripts(runner, client_top, step_)

    result = runner.invoke(
        client_top,
        "step_dependency create "
        "--output yaml "
        f"--prereq_id {steps[0].id} "
        f"--depend_id {steps[1].id} ",
    )
    step_depend = check_and_parse_result(result, models.Dependency)

    assert step_depend.prereq_id == steps[0].id
    assert step_depend.depend_id == steps[1].id
    # depend_is_done = step_depend.is_done(session)
    # assert not depend_is_done

    if level.value <= LevelEnum.step.value:
        return

    gnames = [f"group{i}_{uuid_int}" for i in range(5)]
    groups = []
    for gname_ in gnames:
        result = runner.invoke(
            client_top,
            "group create " "--output yaml " f"--name {gname_} " "--spec_block_name group",
            f"--parent_name {steps[1].fullname}",
        )
        group = check_and_parse_result(result, models.Group)
        groups.append(group)

    for group_ in groups:
        add_scripts(runner, client_top, group_)

    if level.value <= LevelEnum.group.value:
        return

    jobs = []
    for group_ in groups:
        result = runner.invoke(
            client_top,
            "job create " "--output yaml " f"--name job_{uuid_int}" "--spec_block_name job",
            f"--parent_name {group_.fullname}",
        )
        job = check_and_parse_result(result, models.Job)
        jobs.append(job)

    for job_ in jobs:
        add_scripts(runner, client_top, job_)

    return


def delete_all_productions(
    runner: CliRunner,
    client_top: BaseCommand,
) -> None:
    result = runner.invoke(client_top, "production list " "--output yaml")
    productions = check_and_parse_result(result, list[models.Production])

    for prod_ in productions:
        result = runner.invoke(client_top, "production delete " f"--row_id {prod_.id}")
        if not result.exit_code == 0:
            raise ValueError(f"{result} failed with {result.exit_code} {result.output}")


def check_update_methods(
    runner: CliRunner,
    client_top: BaseCommand,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    result = runner.invoke(
        client_top,
        f"{entry_class_name} update data_dict "
        "--output yaml "
        f"--row_id {entry.id} "
        "--update_dict test:dummy",
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "update_data_dict failed"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update data_dict " "--output yaml " "--row_id -1 " "--update_dict test:dummy",
    )
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get data_dict " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    result = runner.invoke(client_top, f"{entry_class_name} get data_dict " "--output yaml " f"--row_id -1")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(client_top, "get obj-data-dict " "--output yaml " f"--fullname {entry.fullname}")
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    result = runner.invoke(client_top, "get obj-data-dict " "--output yaml " "--fullname bad")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update collections "
        "--output yaml "
        f"--row_id {entry.id} "
        "--update_dict test:dummy",
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "update_collections failed"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update collections " "--output yaml " f"--row_id -1 " "--update_dict test:dummy",
    )
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get collections " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_collections failed"

    result = runner.invoke(client_top, f"{entry_class_name} get collections " "--output yaml " "--row_id -1")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(client_top, "get obj-collections " "--output yaml " f"--fullname {entry.fullname}")
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_collections failed"

    result = runner.invoke(client_top, "get obj-collections " "--output yaml " "--fullname bad")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get resolved_collections " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_collections failed"

    result = runner.invoke(
        client_top, f"{entry_class_name} get resolved_collections " "--output yaml " "--row_id -1"
    )
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, "get obj-resolved-collections " "--output yaml " f"--fullname {entry.fullname}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_collections failed"

    result = runner.invoke(client_top, "get obj-resolved-collections " "--output yaml " "--fullname bad")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update child_config "
        f"--row_id {entry.id} "
        "--output yaml "
        "--update_dict test:dummy",
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "update_child_config failed"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update child_config "
        f"--row_id -1 "
        "--output yaml "
        "--update_dict test:dummy",
    )
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get child_config " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_child_config failed"

    result = runner.invoke(client_top, f"{entry_class_name} get child_config " "--output yaml " "--row_id -1")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, "get obj-child-config " "--output yaml " f"--fullname {entry.fullname}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_child_config failed"

    result = runner.invoke(client_top, "get obj-child-config " "--output yaml " "--fullname bad")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update spec_aliases "
        "--output yaml "
        f"--row_id {entry.id} "
        "--update_dict test:dummy",
    )
    # FIXME, type
    check = check_and_parse_result(result, entry_class)
    assert check.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update spec_aliases "
        "--output yaml "
        f"--row_id -1 "
        "--update_dict test:dummy",
    )
    # FIXME
    expect_failed_result(result, 1)

    # FIXME name
    result = runner.invoke(
        client_top, f"{entry_class_name} get spec_alias " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_spec_alias failed"

    result = runner.invoke(client_top, f"{entry_class_name} get spec_alias " "--output yaml " "--row_id -1")
    # FIXME
    # expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, "get obj-spec-aliases " "--output yaml " f"--fullname {entry.fullname}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_spec_aliases failed"

    result = runner.invoke(client_top, "get obj-spec-aliases " "--output yaml " "--fullname bad")
    # FIXME
    # expect_failed_result(result, 1)


def check_scripts(
    runner: CliRunner,
    client_top: BaseCommand,
    entry: models.ElementMixin,
    entry_class_name: str,
) -> None:
    models.ScriptQuery(
        fullname=entry.fullname,
        script_name=None,
    )
    result = runner.invoke(
        client_top, f"{entry_class_name} get scripts " "--output yaml " f"--row_id {entry.id}"
    )
    scripts = check_and_parse_result(result, list[models.Script])
    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} get scripts " "--output yaml " f"--row_id {entry.id} " "--script_name bad",
    )

    no_scripts = check_and_parse_result(result, list[models.Script])
    assert len(no_scripts) == 0, "get_scripts with bad script_name did not return []"

    result = runner.invoke(
        client_top, f"{entry_class_name} get all_scripts " "--output yaml " f"--row_id {entry.id} "
    )
    all_scripts = check_and_parse_result(result, list[models.Script])
    assert len(all_scripts) != 0, "get_all_scripts with failed"


def check_get_methods(
    runner: CliRunner,
    client_top: BaseCommand,
    entry: models.ElementMixin,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
    parent_class: TypeAlias = models.ElementMixin,
) -> None:
    result = runner.invoke(client_top, f"{entry_class_name} get all " "--output yaml " f"--row_id {entry.id}")
    check_get = check_and_parse_result(result, entry_class)

    assert check_get.id == entry.id, "pulled row should be identical"
    assert check_get.level == entry.level, "pulled row db_id should be identical"

    result = runner.invoke(client_top, f"{entry_class_name} get all " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get spec_block " "--output yaml " f"--row_id {entry.id}"
    )
    check_and_parse_result(result, models.SpecBlock)

    result = runner.invoke(client_top, f"{entry_class_name} get spec_block " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)

    """
    result = runner.invoke(
        f"{config.prefix}/get/specification",
        params=get_fullname_model.model_dump(),
    )
    specification = check_and_parse_result(result, models.Specification)

    result = runner.invoke(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/specification",
    )
    specification_check = check_and_parse_result(result, models.Specification)
    assert specification.name == specification_check.name

    result =
      runner.invoke(f"{config.prefix}/{entry_class_name}/get/-1/specification")
    expect_failed_result(result, 404)

    result = runner.invoke(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/tasks",
    )
    check = check_and_parse_result(result, models.MergedTaskSetDict)
    assert len(check.reports) == 0, "length of tasks should be 0"

    result = runner.invoke(f"{config.prefix}/{entry_class_name}/get/-1/tasks")
    expect_failed_result(result, 404)

    result = runner.invoke(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/wms_task_reports",
    )
    check = check_and_parse_result(result, models.MergedWmsTaskReportDict)

    assert len(check.reports) == 0, "length of reports should be 0"
    result =
     client.get(f"{config.prefix}/{entry_class_name}/get/-1/wms_task_reports")
    expect_failed_result(result, 404)

    result = runner.invoke(
        f"{config.prefix}/{entry_class_name}/get/{entry.id}/products",
    )
    check = check_and_parse_result(result, models.MergedProductSetDict)
    assert len(check.reports) == 0, "length of products should be 0"

    result =
      runner.invoke(f"{config.prefix}/{entry_class_name}/get/-1/products")
    expect_failed_result(result, 404)
    """


def check_queue(
    runner: CliRunner,
    client_top: BaseCommand,
    entry: models.ElementMixin,
) -> None:
    # TODO, make and test queue object
    pass
