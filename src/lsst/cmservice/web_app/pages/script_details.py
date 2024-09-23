from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Group, Job, Script, Step
from lsst.cmservice.web_app.utils.utils import map_status


def is_script_collection(collection: tuple[str, str]) -> bool:
    key, value = collection
    return not (
        key.startswith("campaign_")
        or key.startswith("step_")
        or key.startswith("group_")
        or key.startswith("job_")
        or key == "out"
    )


async def get_script_by_id(
    session: async_scoped_session,
    script_id: int,
    campaign_id: int | None = None,
    step_id: int | None = None,
    group_id: int | None = None,
    job_id: int | None = None,
) -> dict[str, Any] | None:
    q = select(Script).where(Script.id == script_id)

    async with session.begin_nested():
        results = await session.scalars(q)
        script = results.one()
        script_details = None

        if script is not None:
            fullname = script.fullname.split("/")
            for i in range(2, len(fullname) - 1):
                match i:
                    case 2:
                        if step_id is None:
                            step_id = await get_step_id_by_fullname(session, "/".join(fullname[:3]))
                    case 3:
                        if group_id is None:
                            group_id = await get_group_id_by_fullname(session, "/".join(fullname[:4]))
                    case 4:
                        print("getting job id")
                        if job_id is None:
                            job_id = await get_job_id_by_fullname(session, "/".join(fullname[:5]))

            collections = await script.resolve_collections(session)
            filtered_collections = dict(
                filter(
                    lambda collection: is_script_collection(collection),
                    collections.items(),
                ),
            )
            script_details = {
                "id": script.id,
                "name": script.name,
                "campaign_id": campaign_id,
                "step_id": step_id,
                "group_id": group_id,
                "job_id": job_id,
                "fullname": script.fullname,
                "superseded": script.superseded,
                "status": map_status(script.status),
                "data": script.data,
                "collections": filtered_collections,
                "child_config": script.child_config,
            }

        return script_details


async def get_step_id_by_fullname(session: async_scoped_session, fullname: str) -> int | None:
    q = select(Step.id).where(Step.fullname == fullname)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.one_or_none()


async def get_group_id_by_fullname(session: async_scoped_session, fullname: str) -> int | None:
    q = select(Group.id).where(Group.fullname == fullname)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.one_or_none()


async def get_job_id_by_fullname(session: async_scoped_session, fullname: str) -> int | None:
    q = select(Job.id).where(Job.fullname == fullname)
    async with session.begin_nested():
        results = await session.scalars(q)
        return results.one_or_none()
