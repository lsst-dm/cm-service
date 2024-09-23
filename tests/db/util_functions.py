from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice import db
from lsst.cmservice.common.enums import LevelEnum
from lsst.cmservice.handlers import interface


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

    if level.value <= LevelEnum.step.value:
        return

    gnames = [f"group{i}_{uuid_int}" for i in range(5)]
    groups = [
        await db.Group.create_row(
            session,
            name=gname_,
            spec_block_name="group",
            parent_name=steps[0].fullname,
        )
        for gname_ in gnames
    ]

    if level.value <= LevelEnum.group.value:
        return

    _ = [
        await db.Job.create_row(
            session,
            name=f"job_{uuid_int}",
            spec_block_name="job",
            parent_name=group_.fullname,
        )
        for group_ in groups
    ]
    return


async def delete_all_productions(
    session: async_scoped_session,
) -> None:
    productions = await db.Production.get_rows(
        session,
    )

    for prod_ in productions:
        await db.Production.delete_row(session, prod_.id)
