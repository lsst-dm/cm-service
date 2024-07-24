from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Script
from lsst.cmservice.common.enums import LevelEnum
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
        c_id = None
        s_id = None
        g_id = None
        j_id = None

        if script is not None:
            if campaign_id is None:
                campaign = await script.get_campaign(session)
                c_id = campaign.id
            parent = await script.get_parent(session)
            if not parent.level == LevelEnum.campaign:
                if parent.level == LevelEnum.step:
                    s_id = script.parent_id if step_id is None else step_id
                elif parent.level == LevelEnum.group:
                    g_id = script.parent_id if step_id is None else group_id
                elif parent.level == LevelEnum.job:
                    j_id = script.parent_id if step_id is None else job_id
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
                "campaign_id": c_id,
                "step_id": s_id,
                "group_id": g_id,
                "job_id": j_id,
                "fullname": script.fullname,
                "superseded": script.superseded,
                "status": map_status(script.status),
                "data": script.data,
                "collections": filtered_collections,
                "child_config": script.child_config,
            }

        return script_details
