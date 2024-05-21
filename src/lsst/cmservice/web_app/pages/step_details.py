# from sqlalchemy import select

from lsst.cmservice.db import Step
from lsst.cmservice.web_app.pages.steps import get_step_details
from lsst.cmservice.web_app.utils.utils import map_status


async def get_step_details_by_id(session, step_id):
    step = await Step.get_row(session, step_id)
    step_details = await get_step_details(session, step)
    groups = await get_step_groups(session, step)
    return step_details, groups


async def get_step_groups(session, step):
    groups = await step.children(session)
    step_groups = []
    for group in groups:
        step_groups.append(
            {
                "id": group.id,
                "name": group.name,
                "superseded": group.superseded,
                "status": map_status(group.status),
                "data": group.data["data_query"],
                "collections": group.collections,
                "child_config": group.child_config,
                "spec_aliases": group.spec_aliases,
            },
        )
    return step_groups
