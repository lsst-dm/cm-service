import pytest
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.handlers import interface


@pytest.mark.asyncio()
async def test_micro(session: async_scoped_session) -> None:
    """Test fake end to end run using example/example_micro.yaml"""

    await interface.load_and_create_campaign(
        session,
        "examples/example_hsc_micro.yaml",
        "hsc_micro",
        "w_2023_41",
        "hsc_micro#campaign",
    )

    changed, status = await interface.process(
        session,
        "hsc_micro/w_2023_41",
        fake_status=StatusEnum.accepted,
    )

    assert changed
    assert status == StatusEnum.accepted

    # now we clean up
    await db.Production.delete_row(session, 1)

    this_spec = await db.Specification.get_row_by_fullname(session, "hsc_micro")
    await db.Specification.delete_row(session, this_spec.id)

    # make sure we cleaned up
    n_campaigns = len(await db.Campaign.get_rows(session))
    n_steps = len(await db.Step.get_rows(session))
    n_groups = len(await db.Group.get_rows(session))
    n_jobs = len(await db.Job.get_rows(session))
    n_scripts = len(await db.Script.get_rows(session))
    n_step_dependencies = len(await db.StepDependency.get_rows(session))
    n_script_dependencies = len(await db.ScriptDependency.get_rows(session))

    assert n_campaigns == 0
    assert n_steps == 0
    assert n_groups == 0
    assert n_jobs == 0
    assert n_scripts == 0

    assert n_step_dependencies == 0
    assert n_script_dependencies == 0
