from typing import Any

from lsst.cmservice.api.web_app.pages.steps import get_step_details
from lsst.cmservice.api.web_app.utils.utils import map_status
from lsst.cmservice.core.common.types import AnyAsyncSession
from lsst.cmservice.core.db import NodeMixin, Step


async def get_step_details_by_id(
    session: AnyAsyncSession,
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


async def get_step_groups(session: AnyAsyncSession, step: Step) -> list[dict]:
    groups = await step.children(session)
    step_groups = [
        {
            "id": group.id,
            "name": group.name,
            "superseded": group.superseded,
            "status": map_status(group.status),
            "org_status": {"name": group.status.name, "value": group.status.value},
            "data": group.data,
            "collections": group.collections,
            "child_config": group.child_config,
            "spec_aliases": group.spec_aliases,
        }
        for group in groups
    ]
    return step_groups


async def get_step_scripts(session: AnyAsyncSession, step: Step) -> list[dict]:
    scripts = await step.get_scripts(session)
    step_scripts = [
        {
            "id": script.id,
            "name": script.name,
            "fullname": script.fullname,
            "superseded": script.superseded,
            "status": str(script.status.name).upper(),
            "log_url": script.log_url,
        }
        for script in scripts
    ]
    return step_scripts


async def get_step_node(session: AnyAsyncSession, step_id: int) -> NodeMixin:
    step = await Step.get_row(session, step_id)
    return step
