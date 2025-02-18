import importlib
from typing import TypeAlias

import pytest
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common import errors
from lsst.cmservice.common.enums import LevelEnum, StatusEnum, TableEnum


async def add_scripts(
    session: async_scoped_session,
    element: db.ElementMixin,
) -> tuple[list[db.Script], db.ScriptDependency]:
    prep_script = await db.Script.create_row(
        session,
        name="prepare",
        parent_name=element.fullname,
        parent_level=element.level,
        spec_block_name="null_script",
    )

    collect_script = await db.Script.create_row(
        session,
        name="collect",
        parent_name=element.fullname,
        parent_level=element.level,
        spec_block_name="null_script",
    )

    script_depend = await db.ScriptDependency.create_row(
        session,
        prereq_id=prep_script.id,
        depend_id=collect_script.id,
    )

    return ([prep_script, collect_script], script_depend)


async def create_tree(
    session: async_scoped_session,
    level: LevelEnum,
    uuid_int: int,
) -> None:
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    specification = await interface.load_specification(session, "examples/empty_config.yaml")
    _ = await specification.get_block(session, "campaign")

    pname = f"prod0_{uuid_int}"
    _ = await db.Production.create_row(session, name=pname)

    cname = f"camp0_{uuid_int}"
    camp = await db.Campaign.create_row(
        session,
        name=cname,
        spec_block_assoc_name="base#campaign",
        parent_name=pname,
    )

    (_camp_scripts, _camp_script_depend) = await add_scripts(session, camp)

    if level.value <= LevelEnum.campaign.value:
        return

    snames = [f"step{i}_{uuid_int}" for i in range(2)]
    steps = [
        await db.Step.create_row(
            session,
            name=sname_,
            spec_block_name="basic_step",
            parent_name=camp.fullname,
        )
        for sname_ in snames
    ]

    for step_ in steps:
        await add_scripts(session, step_)

    step_depend = await db.StepDependency.create_row(
        session,
        prereq_id=steps[0].id,
        depend_id=steps[1].id,
    )

    assert step_depend.prereq_id == steps[0].id
    assert step_depend.depend_id == steps[1].id
    depend_is_done = await step_depend.is_done(session)
    assert not depend_is_done

    if level.value <= LevelEnum.step.value:
        return

    gnames = [f"group{i}_{uuid_int}" for i in range(5)]
    groups = [
        await db.Group.create_row(
            session,
            name=gname_,
            spec_block_name="group",
            parent_name=steps[1].fullname,
        )
        for gname_ in gnames
    ]

    for group_ in groups:
        await add_scripts(session, group_)

    if level.value <= LevelEnum.group.value:
        return

    jobs_ = [
        await db.Job.create_row(
            session,
            name=f"job_{uuid_int}",
            spec_block_name="job",
            parent_name=group_.fullname,
        )
        for group_ in groups
    ]

    for job in jobs_:
        await add_scripts(session, job)

    return


async def delete_all_rows(
    session: async_scoped_session,
    table_class: TypeAlias = db.RowMixin,
) -> None:
    rows = await table_class.get_rows(session)
    for row_ in rows:
        await table_class.delete_row(session, row_.id)

    rows_check = await table_class.get_rows(session)
    assert len(rows_check) == 0, f"Failed to delete all {table_class}"


async def delete_all_productions(
    session: async_scoped_session,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_rows(session, db.Production)
    if check_cascade:
        n_campaigns = len(await db.Campaign.get_rows(session))
        n_steps = len(await db.Step.get_rows(session))
        n_groups = len(await db.Group.get_rows(session))
        n_jobs = len(await db.Job.get_rows(session))
        n_scripts = len(await db.Script.get_rows(session))
        assert n_campaigns == 0
        assert n_steps == 0
        assert n_groups == 0
        assert n_jobs == 0
        assert n_scripts == 0


async def delete_all_spec_stuff(
    session: async_scoped_session,
) -> None:
    await delete_all_rows(session, db.Specification)
    await delete_all_rows(session, db.SpecBlock)
    await delete_all_rows(session, db.ScriptTemplate)


async def delete_all_queues(
    session: async_scoped_session,
) -> None:
    await delete_all_rows(session, db.Queue)


async def cleanup(
    session: async_scoped_session,
    *,
    check_cascade: bool = False,
) -> None:
    await delete_all_productions(session, check_cascade=check_cascade)
    await delete_all_spec_stuff(session)
    await delete_all_queues(session)

    await session.commit()
    await session.close()
    await session.remove()


async def check_update_methods(
    session: async_scoped_session,
    entry: db.NodeMixin,
    entry_class: TypeAlias = db.ElementMixin,
) -> None:
    check = await entry.update_data_dict(
        session,
        test="dummy",
    )
    assert check.data["test"] == "dummy", "update_data_dict failed"

    check = await entry.update_collections(
        session,
        test="dummy",
    )
    assert check.collections["test"] == "dummy", "update_collections failed"

    check = await entry.update_child_config(
        session,
        test="dummy",
    )
    assert check.child_config["test"] == "dummy", "update_child_config failed"

    check = await entry.update_spec_aliases(
        session,
        test="dummy",
    )
    assert check.spec_aliases["test"] == "dummy", "update_spec_aliases failed"

    await entry.update_values(
        session,
        status=StatusEnum.accepted,
    )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_data_dict(
            session,
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_collections(
            session,
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_child_config(
            session,
            test="dummy",
        )

    with pytest.raises(errors.CMBadStateTransitionError):
        check = await entry.update_spec_aliases(
            session,
            test="dummy",
        )

    # play around with status
    await entry.update_values(
        session,
        status=StatusEnum.reviewable,
    )

    check = await entry.reject(session)
    assert check.status == StatusEnum.rejected, "reject() failed"

    check = await entry.reset(session)
    assert check.status == StatusEnum.waiting, "reset() failed"

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.accept(session)

    await entry.update_values(
        session,
        status=StatusEnum.running,
    )
    check = await entry.accept(session)

    assert check.status == StatusEnum.accepted, "accept() failed"

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.delete_row(session, entry.id)

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.reject(session)

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.reset(session)

    with pytest.raises(errors.CMIDMismatchError):
        await entry.update_row(session, id=99, row_id=entry.id)

    with pytest.raises(errors.CMMissingIDError):
        await entry.update_row(session, id=99, row_id=99)

    await entry.update_row(session, row_id=entry.id, dummy=None)

    check_update = await entry_class.update_row(session, entry.id, data=dict(foo="bar"))
    assert check_update.data["foo"] == "bar", "foo value should be bar"

    check_update2 = await check_update.update_values(session, data=dict(bar="foo"))
    assert check_update2.data["bar"] == "foo", "bar value should be foo"


async def check_scripts(
    session: async_scoped_session,
    entry: db.ElementMixin,
) -> None:
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    scripts = await entry.get_scripts(session)
    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    for script_ in scripts:
        parent_check = await script_.get_parent(session)
        assert parent_check.id == entry.id, "Script parent id mismatch"

    prereq_0 = await scripts[0].check_prerequisites(session)
    assert prereq_0, "check_prerequisites is False for first script"

    prereq_1 = await scripts[1].check_prerequisites(session)
    assert not prereq_1, "check_prerequisites is True for second script"

    no_scripts = await entry.get_scripts(session, script_name="bad")
    assert len(no_scripts) == 0, "get_scripts with bad script_name did not return []"

    all_scripts = await entry.get_all_scripts(session)
    assert len(all_scripts) != 0, "get_all_scripts with failed"

    await scripts[1].update_values(session, status=StatusEnum.running)
    sleep_time = await entry.estimate_sleep_time(session)
    assert sleep_time == 30, "Wrong sleep time for element with running script"

    sleep_time = await scripts[1].estimate_sleep_time(session)
    assert sleep_time == 30, "Wrong sleep time for running script"

    await scripts[1].update_values(session, status=StatusEnum.waiting, superseded=True)
    scripts_check = await entry.get_scripts(session)

    assert len(scripts_check) == 1, "Failed to ignore superseded script"

    script_iface_check = await interface.get_node_by_fullname(
        session,
        f"script:{scripts[1].fullname}",
    )
    assert script_iface_check.id == scripts[1].id

    scripts_check = await entry.get_scripts(session, skip_superseded=False)
    assert len(scripts_check) == 2, "Failed to respect skip_superseded"

    await scripts[1].update_values(session, superseded=False)

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.retry_script(session, "prepare")

    with pytest.raises(errors.CMTooManyActiveScriptsError):
        await entry.retry_script(session, "bad")

    await scripts[0].update_values(session, status=StatusEnum.running)
    await scripts[0].process(session, fake_status=StatusEnum.failed)

    check = await entry.retry_script(session, "prepare")
    assert check.status == StatusEnum.waiting, "Failed to retry script"

    await scripts[0].update_values(session, status=StatusEnum.failed)

    with pytest.raises(errors.CMBadStateTransitionError):
        await interface.reset_script(session, scripts[0].fullname, StatusEnum.accepted)

    check = await interface.reset_script(session, scripts[0].fullname, StatusEnum.prepared)
    assert check.status == StatusEnum.prepared, "Failed to reset script to prepared"

    check = await interface.reset_script(session, scripts[0].fullname, StatusEnum.ready)
    assert check.status == StatusEnum.ready, "Failed to reset script to ready"

    with pytest.raises(errors.CMBadStateTransitionError):
        await interface.reset_script(session, scripts[0].fullname, StatusEnum.prepared)

    check = await interface.reset_script(session, scripts[0].fullname, StatusEnum.waiting)
    assert check.status == StatusEnum.waiting, "Failed to reset script to waiting"

    sleep_time = await scripts[0].estimate_sleep_time(session)
    assert sleep_time == 10

    await scripts[0].update_values(session, status=StatusEnum.accepted)
    with pytest.raises(errors.CMBadStateTransitionError):
        await interface.reset_script(session, scripts[0].fullname, StatusEnum.waiting)


async def check_get_methods(
    session: async_scoped_session,
    entry: db.ElementMixin,
    entry_class: TypeAlias = db.ElementMixin,
    parent_class: TypeAlias = db.ElementMixin,
) -> None:
    interface = importlib.import_module("lsst.cmservice.handlers.interface")
    check_getall_nonefound = await entry_class.get_rows(
        session,
        parent_name="bad",
        parent_class=parent_class,
    )
    assert len(check_getall_nonefound) == 0, "length should be 0"

    check_get = await entry_class.get_row(session, entry.id)
    assert check_get.id == entry.id, "pulled row should be identical"

    with pytest.raises(errors.CMMissingIDError):
        await entry_class.get_row(
            session,
            -99,
        )

    check_iface = await interface.get_node_by_fullname(session, entry.fullname)
    assert check_iface.id == entry.id, "pulled row using interface should be identical"

    check_get_by_name = await entry_class.get_row_by_name(session, name=entry.name)
    assert check_get_by_name.id == entry.id, "pulled row should be identical"

    with pytest.raises(errors.CMMissingFullnameError):
        await entry_class.get_row_by_name(session, name="foo")

    check_get_by_fullname = await entry_class.get_row_by_fullname(session, entry.fullname)
    assert check_get_by_fullname.id == entry.id, "pulled row should be identical"

    with pytest.raises(errors.CMBadEnumError):
        await interface.get_row_by_table_and_id(session, entry.id, TableEnum.n_tables)

    with pytest.raises(errors.CMMissingFullnameError):
        await interface.get_row_by_table_and_id(session, -99, TableEnum[entry.__tablename__])  # type: ignore

    with pytest.raises(errors.CMBadEnumError):
        await interface.get_node_by_level_and_id(session, entry.id, LevelEnum.n_levels)

    with pytest.raises(errors.CMMissingFullnameError):
        await interface.get_node_by_level_and_id(session, -99, entry.level)

    check = await interface.get_row_by_table_and_id(
        session,
        entry.id,
        TableEnum[entry.__tablename__],  # type: ignore
    )
    assert check.fullname == entry.fullname

    check = await interface.get_node_by_level_and_id(
        session,
        entry.id,
        entry.level,
    )
    assert check.fullname == entry.fullname

    spec_block_check = await entry.get_spec_block(session)
    assert spec_block_check.name

    specification_check = await entry.get_specification(session)
    assert specification_check.name

    check1 = await entry.get_tasks(session)
    assert len(check1.reports) == 0, "length of tasks should be 0"

    check2 = await entry.get_wms_reports(session)
    assert len(check2.reports) == 0, "length of reports should be 0"

    check3 = await entry.get_products(session)
    assert len(check3.reports) == 0, "length of products should be 0"

    sleep_time = await entry.estimate_sleep_time(session)
    assert sleep_time == 10, "Wrong sleep time"


async def check_queue(
    session: async_scoped_session,
    entry: db.ElementMixin,
) -> None:
    # make and test queue object
    queue = await db.Queue.create_row(session, fullname=entry.fullname)

    check_elem = await queue.get_node(session)
    assert check_elem.id == entry.id

    check_queue_item = await db.Queue.get_queue_item(session, fullname=entry.fullname)
    assert check_queue_item.node_id == entry.id

    queue.waiting()

    sleep_time = await queue.node_sleep_time(session)
    assert sleep_time == 10

    scripts = await entry.get_scripts(session)
    script = scripts[0]
    queue_script = await db.Queue.create_row(session, fullname=f"script:{script.fullname}")

    check_script = await queue_script.get_node(session)
    assert check_script.id == script.id

    check_queue_script_item = await db.Queue.get_queue_item(session, fullname=f"script:{script.fullname}")
    assert check_queue_script_item.node_id == script.id

    await db.Queue.delete_row(session, queue.id)
