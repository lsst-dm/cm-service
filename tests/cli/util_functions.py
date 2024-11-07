from typing import TypeAlias, TypeVar

import yaml
from click import BaseCommand
from click.testing import CliRunner, Result
from pydantic import TypeAdapter

from lsst.cmservice import models
from lsst.cmservice.common.enums import LevelEnum, StatusEnum

T = TypeVar("T")


def check_and_parse_result(
    result: Result,
    return_class: type[T],
) -> T:
    if not result.exit_code == 0:
        raise ValueError(f"{result} failed with {result.exit_code} {result.output}")
    return_obj = TypeAdapter(return_class).validate_python(yaml.unsafe_load(result.stdout))
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

    step_0 = steps[0]
    step_1 = steps[1]

    result = runner.invoke(
        client_top,
        "step_dependency create " "--output yaml " f"--prereq_id {step_0.id} " f"--depend_id {step_1.id} ",
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
            "group create "
            "--output yaml "
            f"--name {gname_} "
            "--spec_block_name group "
            f"--parent_name {step_1.fullname}",
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
            "job create "
            "--output yaml "
            f"--name job_{uuid_int} "
            "--spec_block_name job "
            f"--parent_name {group_.fullname}",
        )
        job = check_and_parse_result(result, models.Job)
        jobs.append(job)

    for job_ in jobs:
        add_scripts(runner, client_top, job_)

    return


def delete_all_rows(
    runner: CliRunner,
    client_top: BaseCommand,
    entry_class_name: str,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    result = runner.invoke(client_top, f"{entry_class_name} list " "--output yaml")
    rows = check_and_parse_result(result, list[entry_class])

    for row_ in rows:
        result = runner.invoke(client_top, f"{entry_class_name} delete " f"--row_id {row_.id}")
        if not result.exit_code == 0:
            raise ValueError(f"{result} failed with {result.exit_code} {result.output}")


def delete_all_productions(
    runner: CliRunner,
    client_top: BaseCommand,
    *,
    check_cascade: bool = False,
) -> None:
    delete_all_rows(runner, client_top, "production", models.Production)
    if check_cascade:
        result = runner.invoke(client_top, "campaign list " "--output yaml")
        n_campaigns = len(check_and_parse_result(result, list[models.Campaign]))
        result = runner.invoke(client_top, "step list " "--output yaml")
        n_steps = len(check_and_parse_result(result, list[models.Step]))
        assert n_campaigns == 0
        assert n_steps == 0


def delete_all_spec_stuff(
    runner: CliRunner,
    client_top: BaseCommand,
) -> None:
    delete_all_rows(runner, client_top, "specification", models.Specification)
    delete_all_rows(runner, client_top, "spec_block", models.SpecBlock)
    delete_all_rows(runner, client_top, "script_template", models.ScriptTemplate)


def delete_all_queues(
    runner: CliRunner,
    client_top: BaseCommand,
) -> None:
    delete_all_rows(runner, client_top, "queue", models.Queue)


def cleanup(
    runner: CliRunner,
    client_top: BaseCommand,
    *,
    check_cascade: bool = False,
) -> None:
    delete_all_productions(runner, client_top, check_cascade=check_cascade)
    delete_all_spec_stuff(runner, client_top)
    delete_all_queues(runner, client_top)


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
        client_top,
        f"{entry_class_name} update all " "--output yaml " f"--row_id {entry.id} " "--data test:dummy",
    )
    check_update = check_and_parse_result(result, entry_class)
    assert check_update.data["test"] == "dummy", "update all failed"

    result = runner.invoke(
        client_top, f"{entry_class_name} get data_dict " "--output yaml " f"--row_id {entry.id}"
    )
    check = check_and_parse_result(result, dict)
    assert check["test"] == "dummy", "get_data_dict failed"

    result = runner.invoke(client_top, f"{entry_class_name} get data_dict " "--output yaml " f"--row_id -1")
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
        client_top,
        f"{entry_class_name} update spec_aliases "
        "--output yaml "
        f"--row_id {entry.id} "
        "--update_dict test:dummy",
    )
    # FIXME, type
    check_spec = check_and_parse_result(result, entry_class)
    assert check_spec.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    result = runner.invoke(
        client_top,
        f"{entry_class_name} update spec_aliases " "--output yaml " "--row_id -1 " "--update_dict test:dummy",
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

    script0 = scripts[0]

    result = runner.invoke(
        client_top,
        f"script update status --status failed --row_id {script0.id} --output yaml",
    )
    assert result.exit_code == 0

    result = runner.invoke(
        client_top,
        f"script action reset --row_id {script0.id} --output yaml",
    )
    reset_script = check_and_parse_result(result, models.Script)
    assert reset_script.status == StatusEnum.waiting

    result = runner.invoke(
        client_top,
        f"script update status --status failed --row_id {script0.id} --output yaml",
    )
    assert result.exit_code == 0

    result = runner.invoke(
        client_top,
        f"action reset-script --fullname {script0.fullname} --status waiting --output yaml",
    )
    reset_script = check_and_parse_result(result, models.Script)
    assert reset_script.status == StatusEnum.waiting

    result = runner.invoke(
        client_top,
        f"script update status --status failed --row_id {script0.id} --output yaml",
    )
    assert result.exit_code == 0

    result = runner.invoke(
        client_top,
        f"{entry_class_name} action retry_script "
        f"--row_id {entry.id} --script_name {script0.name} --output yaml",
    )
    retry_script = check_and_parse_result(result, models.Script)
    assert retry_script.status == StatusEnum.waiting

    result = runner.invoke(
        client_top,
        f"script get script-errors --row_id {script0.id} --output yaml",
    )
    check_errors = check_and_parse_result(result, list[models.ScriptError])
    assert len(check_errors) == 0


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

    result = runner.invoke(
        client_top, f"{entry_class_name} get by_name " "--output yaml " f"--name {entry.name}"
    )
    check_get = check_and_parse_result(result, entry_class)
    assert check_get.id == entry.id, "pulled row should be identical"

    result = runner.invoke(
        client_top, f"{entry_class_name} get by_fullname " "--output yaml " f"--fullname {entry.fullname}"
    )
    check_get = check_and_parse_result(result, entry_class)
    assert check_get.id == entry.id, "pulled row should be identical"

    result = runner.invoke(client_top, f"{entry_class_name} get all " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get spec_block " "--output yaml " f"--row_id {entry.id}"
    )
    check_and_parse_result(result, models.SpecBlock)

    result = runner.invoke(client_top, f"{entry_class_name} get spec_block " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get specification " "--output yaml " f"--row_id {entry.id}"
    )
    check_and_parse_result(result, models.Specification)

    result = runner.invoke(
        client_top, f"{entry_class_name} get specification " "--output yaml " "--row_id -1"
    )
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get tasks " "--output yaml " f"--row_id {entry.id}"
    )
    check_tasks = check_and_parse_result(result, list[models.MergedTaskSet])
    assert len(check_tasks) == 0, "length of tasks should be 0"

    result = runner.invoke(client_top, f"{entry_class_name} get tasks " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get wms_task_reports " "--output yaml " f"--row_id {entry.id}"
    )
    check_wms_reports = check_and_parse_result(result, list[models.MergedWmsTaskReport])
    assert len(check_wms_reports) == 0, "length of wms_task_reports should be 0"

    result = runner.invoke(
        client_top, f"{entry_class_name} get wms_task_reports " "--output yaml " "--row_id -1"
    )
    expect_failed_result(result, 1)

    result = runner.invoke(
        client_top, f"{entry_class_name} get products " "--output yaml " f"--row_id {entry.id}"
    )
    check_products = check_and_parse_result(result, list[models.MergedProductSet])
    assert len(check_products) == 0, "length of wms_task_reports should be 0"

    result = runner.invoke(client_top, f"{entry_class_name} get products " "--output yaml " "--row_id -1")
    expect_failed_result(result, 1)


def check_queue(
    runner: CliRunner,
    client_top: BaseCommand,
    entry: models.ElementMixin,
    *,
    run_daemon: bool = False,
) -> None:
    result = runner.invoke(client_top, f"queue create --output yaml --interval 0 --fullname {entry.fullname}")
    check = check_and_parse_result(result, models.Queue)

    if run_daemon:
        result = runner.invoke(client_top, f"queue update all --interval 0 --row_id {check.id}")
        assert result.exit_code == 0

        result = runner.invoke(client_top, f"queue daemon --row_id {check.id}")
        assert result.exit_code == 0

    result = runner.invoke(client_top, f"queue delete --row_id {check.id}")
