from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Step
from lsst.cmservice.web_app.pages.steps import get_step_details
from lsst.cmservice.web_app.utils.utils import map_status


async def get_step_details_by_id(session: async_scoped_session, step_id: int) -> (dict, dict, dict):
    step = await Step.get_row(session, step_id)
    collections = await step.resolve_collections(session)
    step_details = await get_step_details(session, step)
    # get step dicts
    step_details["collections"] = collections
    step_details["data"] = step.data
    step_details["child_config"] = step.child_config
    groups = await get_step_groups(session, step)
    scripts = await get_step_scripts(session, step)
    return step_details, groups, scripts


async def get_step_groups(session: async_scoped_session, step: Step) -> [dict]:
    groups = await step.children(session)
    step_groups = []
    for group in groups:
        print(group.spec_aliases)
        step_groups.append(
            {
                "id": group.id,
                "name": group.name,
                "superseded": group.superseded,
                "status": map_status(group.status),
                "data": group.data,
                "collections": group.collections,
                "child_config": group.child_config,
                "spec_aliases": group.spec_aliases,
            },
        )
    return step_groups


async def get_step_scripts(session: async_scoped_session, step: Step) -> [dict]:
    scripts = await step.get_scripts(session)
    step_scripts = []
    for script in scripts:
        step_scripts.append(
            {
                "id": script.id,
                "name": script.name,
                "superseded": script.superseded,
                "status": map_status(script.status),
            },
        )
    return step_scripts
