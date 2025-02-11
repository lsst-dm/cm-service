from typing import Any

from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import NodeMixin, Step
from lsst.cmservice.web_app.pages.steps import get_step_details
from lsst.cmservice.web_app.utils.utils import map_status


async def get_step_details_by_id(
    session: async_scoped_session,
    step_id: int,
) -> tuple[Any, list[dict[Any, Any]], list[dict[Any, Any]]]:
    step = await Step.get_row(session, step_id)
    collections = await step.resolve_collections(session, throw_overrides=False)
    step_details = await get_step_details(session, step)
    # get step dicts
    step_details["collections"] = {key: collections[key] for key in collections if key.startswith("step_")}
    step_details["data"] = step.data
    step_details["child_config"] = step.child_config
    groups = await get_step_groups(session, step)
    scripts = await get_step_scripts(session, step)
    return step_details, groups, scripts


async def get_step_groups(session: async_scoped_session, step: Step) -> list[dict]:
    groups = await step.children(session)
    step_groups = []
    for group in groups:
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


async def get_step_scripts(session: async_scoped_session, step: Step) -> list[dict]:
    scripts = await step.get_scripts(session)
    step_scripts = []
    for script in scripts:
        step_scripts.append(
            {
                "id": script.id,
                "name": script.name,
                "fullname": script.fullname,
                "superseded": script.superseded,
                "status": str(script.status.name).upper(),
                "log_url": script.log_url,
            },
        )
    return step_scripts


async def update_collections(
    session: async_scoped_session, step_id: int, step_collections: dict
) -> NodeMixin:
    step = await Step.get_row(session, step_id)
    updated_step = await step.update_collections(session, **step_collections)
    return updated_step


async def update_child_config(session: async_scoped_session, step_id: int, child_config: dict) -> NodeMixin:
    step = await Step.get_row(session, step_id)
    updated_step = await step.update_child_config(session, **child_config)
    return updated_step


async def get_step_node(session: async_scoped_session, step_id: int) -> NodeMixin:
    step = await Step.get_row(session, step_id)
    return step
