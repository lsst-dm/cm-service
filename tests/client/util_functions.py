from typing import TypeAlias, TypeVar

from lsst.cmservice import models
from lsst.cmservice.client import CMCampaignClient, CMClient, CMGroupClient, CMJobClient, CMStepClient
from lsst.cmservice.common.enums import LevelEnum, StatusEnum

T = TypeVar("T")


def add_scripts(
    client: CMClient,
    element: models.ElementMixin,
) -> tuple[list[models.Script], models.Dependency]:
    prep_script = client.script.create(
        name="prepare",
        parent_name=element.fullname,
        parent_level=element.level,
        spec_block_name="null_script",
    )

    collect_script = client.script.create(
        name="collect",
        parent_name=element.fullname,
        parent_level=element.level,
        spec_block_name="null_script",
    )

    script_depend = client.script_dependency.create(
        prereq_id=prep_script.id,
        depend_id=collect_script.id,
    )

    return ([prep_script, collect_script], script_depend)


def create_tree(
    client: CMClient,
    level: LevelEnum,
    uuid_int: int,
) -> None:
    client.load.specification(
        yaml_file="examples/empty_config.yaml",
    )
    # _ = await specification.get_block("campaign")

    pname = f"prod0_{uuid_int}"
    _ = client.production.create(name=pname)

    cname = f"camp0_{uuid_int}"
    camp = client.campaign.create(
        name=cname,
        spec_block_assoc_name="base#campaign",
        parent_name=pname,
    )

    (camp_scripts, camp_script_depend) = add_scripts(client, camp)

    if level.value <= LevelEnum.campaign.value:
        return

    snames = [f"step{i}_{uuid_int}" for i in range(2)]
    steps = [
        client.step.create(
            name=sname_,
            spec_block_name="basic_step",
            parent_name=camp.fullname,
        )
        for sname_ in snames
    ]

    for step_ in steps:
        add_scripts(client, step_)

    step_depend = client.step_dependency.create(
        prereq_id=steps[0].id,
        depend_id=steps[1].id,
    )

    assert step_depend.prereq_id == steps[0].id
    assert step_depend.depend_id == steps[1].id
    # depend_is_done = await step_depend.is_done()
    # assert not depend_is_done

    if level.value <= LevelEnum.step.value:
        return

    gnames = [f"group{i}_{uuid_int}" for i in range(5)]
    groups = [
        client.group.create(
            name=gname_,
            spec_block_name="group",
            parent_name=steps[1].fullname,
        )
        for gname_ in gnames
    ]

    for group_ in groups:
        add_scripts(client, group_)

    if level.value <= LevelEnum.group.value:
        return

    jobs = [
        client.job.create(
            name=f"job_{uuid_int}",
            spec_block_name="job",
            parent_name=group_.fullname,
        )
        for group_ in groups
    ]

    for job_ in jobs:
        add_scripts(client, job_)

    return


def delete_all_productions(
    client: CMClient,
) -> None:
    productions = client.production.get_rows()

    for prod_ in productions:
        client.production.delete(prod_.id)


def check_update_methods(
    client: CMCampaignClient | CMStepClient | CMGroupClient | CMJobClient,
    entry: models.ElementMixin,
    entry_class: TypeAlias = models.ElementMixin,
) -> None:
    check = client.update_data_dict(
        entry.id,
        test="dummy",
    )
    assert check.data["test"] == "dummy", "update_data_dict failed"

    check = client.update_collections(
        entry.id,
        test="dummy",
    )
    assert check.collections["test"] == "dummy", "update_collections failed"

    check = client.update_child_config(
        entry.id,
        test="dummy",
    )
    check.child_config["test"] == "dummy", "update_child_config failed"

    check = client.update_spec_aliases(
        entry.id,
        test="dummy",
    )
    check.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    check = client.update_status(
        entry.id,
        status=StatusEnum.rejected,
    )
    assert check.status == StatusEnum.rejected, "interface.update_status failed"

    client.update(
        entry.id,
        status=StatusEnum.accepted,
    )

    """
    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_data_dict(
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_collections(
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_child_config(
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_spec_aliases(
            test="dummy",
        )

    # play around with status
    await entry.update_values(
        status=StatusEnum.reviewable,
    )

    check = await entry.reject()
    assert check.status == StatusEnum.rejected, "reject() failed"

    check = await entry.reset()
    assert check.status == StatusEnum.waiting, "reset() failed"

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.accept()

    await entry.update_values(
        session,
        status=StatusEnum.running,
    )
    check = await entry.accept()

    assert check.status == StatusEnum.accepted, "accept() failed"

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.delete_row(session, entry.id)

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.reject()

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.reset()

    with pytest.raises(errors.CMIDMismatchError):
        await entry.update_row(session, id=99, row_id=entry.id)

    with pytest.raises(errors.CMMissingIDError):
        await entry.update_row(session, id=99, row_id=99)

    await entry.update_row(session, row_id=entry.id, dummy=None)

    check_update = await entry_class.update_row(entry.id, data=dict(foo="bar"))
    assert check_update.data["foo"] == "bar", "foo value should be bar"

    check_update2 = await check_update.update_values(data=dict(bar="foo"))
    assert check_update2.data["bar"] == "foo", "bar value should be foo"
    """


def check_scripts(
    client: CMClient,
    sub_client: CMCampaignClient | CMStepClient | CMGroupClient | CMJobClient,
    entry: models.ElementMixin,
) -> None:
    scripts = sub_client.get_scripts(entry.id)
    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    for script_ in scripts:
        assert script_.level == LevelEnum.script, f"Bad script level {script_.db_id.level}"
        # parent_check = await script_.get_parent(session)
        # assert parent_check.id == entry.id, "Script parent id mismatch"

    prereq_0 = client.scripts.check_prerequisites(scripts[0].id)
    assert prereq_0, "check_prerequisites is False for first script"

    prereq_1 = client.scripts.check_prerequisites(scripts[1].id)
    assert not prereq_1, "check_prerequisites is True for second script"

    no_scripts = sub_client.get_scripts(entry.id, script_name="bad")
    assert len(no_scripts) == 0, "get_scripts with bad script_name did not return []"

    all_scripts = sub_client.get_all_scripts(entry.id)
    assert len(all_scripts) != 0, "get_all_scripts with failed"

    client.scripts.update(scripts[1].id, superseded=True)
    scripts_check = sub_client.get_scripts(entry.id)
    assert len(scripts_check) == 1, "Failed to ignore superseded script"

    scripts_check = sub_client.get_scripts(entry.id, skip_superseded=False)
    assert len(scripts_check) == 2, "Failed to respect skip_superseded"

    client.script.update(scripts[1].id, superseded=False)

    # with pytest.raises(errors.CMBadStateTransitionError):
    #    await entry.retry_script(session, "prepare")

    # with pytest.raises(errors.CMTooManyActiveScriptsError):
    #    await entry.retry_script(session, "bad")

    client.script.update(scripts[0].id, status=StatusEnum.failed)

    check = client.retry_script(entry.id, "prepare")
    assert check.status == StatusEnum.waiting, "Failed to retry script"


def check_get_methods(
    sub_client: CMCampaignClient | CMStepClient | CMGroupClient | CMJobClient,
    entry: models.ElementMixin,
    entry_class: TypeAlias = models.ElementMixin,
    parent_class: TypeAlias = models.ElementMixin,
) -> None:
    check_getall_nonefound = sub_client.get_rows(
        parent_name="bad",
        parent_class=parent_class,
    )
    assert len(check_getall_nonefound) == 0, "length should be 0"

    check_get = sub_client.get_row(entry.id)
    assert check_get.id == entry.id, "pulled row should be identical"
    assert check_get.level == entry.level, "pulled row db_id should be identical"

    # with pytest.raises(errors.CMMissingIDError):
    #    await entry_class.get_row(
    #        session,
    #        -99,
    #    )

    check_get_by_name = sub_client.get_row_by_name(name=entry.name)
    assert check_get_by_name.id == entry.id, "pulled row should be identical"

    # with pytest.raises(errors.CMMissingFullnameError):
    #    await entry_class.get_row_by_name(session, name="foo")

    check_get_by_fullname = sub_client.get_row_by_fullname(entry.fullname)
    assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

    sub_client.get_specification(entry.id)
    # assert specification.name == specification_check.name

    check = sub_client.get_tasks(entry.id)
    assert len(check.reports) == 0, "length of tasks should be 0"

    check = sub_client.get_wms_reports(entry.id)
    assert len(check.reports) == 0, "length of reports should be 0"

    check = sub_client.get_products(entry.id)
    assert len(check.reports) == 0, "length of products should be 0"

    sleep_time = sub_client.estimate_sleep_time(entry.id)
    assert sleep_time == 10, "Wrong sleep time"


def check_queue(
    client: CMClient,
    entry: models.ElementMixin,
) -> None:
    # TODO make and test queue object
    pass
