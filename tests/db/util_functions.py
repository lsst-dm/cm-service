import pytest
from sqlalchemy.ext.asyncio import async_scoped_session

import lsst.cmservice.common.errors as errors
from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum, StatusEnum
from lsst.cmservice.handlers import interface


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

    (camp_scripts, camp_script_depend) = await add_scripts(session, camp)

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

    assert step_depend.prereq_db_id.id == steps[0].id
    assert step_depend.depend_db_id.id == steps[1].id
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

    jobs = [
        await db.Job.create_row(
            session,
            name=f"job_{uuid_int}",
            spec_block_name="job",
            parent_name=group_.fullname,
        )
        for group_ in groups
    ]

    for job_ in jobs:
        await add_scripts(session, job_)

    return


async def delete_all_productions(
    session: async_scoped_session,
) -> None:
    productions = await db.Production.get_rows(
        session,
    )

    for prod_ in productions:
        await db.Production.delete_row(session, prod_.id)


async def check_update_methods(
    session: async_scoped_session,
    entry: db.NodeMixin,
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

    with pytest.raises(errors.CMMissingFullnameError):
        await entry.update_row(session, id=99, row_id=99)

    await entry.update_row(session, row_id=entry.id, dummy=None)


async def check_scripts(
    session: async_scoped_session,
    entry: db.ElementMixin,
) -> None:
    scripts = await entry.get_scripts(session)

    assert len(scripts) == 2, f"Expected exactly two scripts for {entry.fullname} got {len(scripts)}"

    for script_ in scripts:
        assert script_.db_id.level == LevelEnum.script, f"Bad script level {script_.db_id.level}"
        assert script_.parent_db_id.level == entry.level, "Script parent level mismatch"

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

    await scripts[1].update_values(session, superseded=True)
    scripts_check = await entry.get_scripts(session)

    assert len(scripts_check) == 1, "Failed to ignore superseded script"

    scripts_check = await entry.get_scripts(session, skip_superseded=False)
    assert len(scripts_check) == 2, "Failed to respect skip_superseded"

    await scripts[1].update_values(session, superseded=False)

    with pytest.raises(errors.CMBadStateTransitionError):
        await entry.retry_script(session, "prepare")

    with pytest.raises(errors.CMTooManyActiveScriptsError):
        await entry.retry_script(session, "bad")

    await scripts[0].update_values(session, status=StatusEnum.failed)

    check = await entry.retry_script(session, "prepare")
    assert check.status == StatusEnum.waiting, "Failed to retry script"
