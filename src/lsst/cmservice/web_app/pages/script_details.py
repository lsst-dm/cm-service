from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Script
from lsst.cmservice.web_app.utils.utils import map_status


async def get_script_by_id(
    session: async_scoped_session,
    script_id: int,
) -> dict[str, Any] | None:
    q = select(Script).where(Script.id == script_id)

    async with session.begin_nested():
        results = await session.scalars(q)
        script = results.one()
        script_details = None

        if script is not None:
            collections = await script.resolve_collections(session)
            script_details = {
                "id": script.id,
                "name": script.name,
                "fullname": script.fullname,
                "superseded": script.superseded,
                "status": map_status(script.status),
                "data": script.data,
                "collections": {"run": collections["run"]},
                "child_config": script.child_config,
            }

        return script_details
