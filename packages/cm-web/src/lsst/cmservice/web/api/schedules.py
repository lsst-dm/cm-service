from collections.abc import AsyncGenerator
from uuid import UUID

from nicegui import app

from lsst.cmservice.models.api.schedules import ScheduleUpdate
from lsst.cmservice.models.db.schedules import CreateManifestTemplate, CreateSchedule

from ..lib.client_factory import CLIENT_FACTORY


async def get_schedule_summary(schedule_id: str | None = None) -> AsyncGenerator[dict]:
    """Gets a list of schedules or a single schedule known to the API."""
    url = "/schedules"
    if schedule_id is not None:
        url += f"/{schedule_id}"

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(url)
        r.raise_for_status()

    for schedule in r.json():
        yield schedule


async def patch_schedule(schedule_id: str | UUID, patch_data: ScheduleUpdate) -> None:
    """PATCH a schedule to toggle its enabled status."""
    actor = app.storage.client["state"].user.username
    async with CLIENT_FACTORY.aclient() as client:
        client.headers["X-Auth-Request-User"] = actor
        r = await client.patch(f"/schedules/{schedule_id}", json=patch_data.model_dump(exclude_unset=True))
        r.raise_for_status()


async def get_schedule_templates(schedule_id: str | UUID) -> AsyncGenerator[CreateManifestTemplate]:
    """Read a collection of manifest template objects for a given schedule from
    the API.
    """
    async with CLIENT_FACTORY.aclient() as client:
        r = await client.get(f"/schedules/{schedule_id}/templates")
        r.raise_for_status()

        for template in r.json():
            yield CreateManifestTemplate(**template)


async def post_new_schedule(schedule: CreateSchedule) -> bool:
    """POSTs a new schedule object to the schedules API. The schedule should
    conform to the API model for schedule creation with 0 or more manifest
    templates.
    """
    # Templates are excluded by default when serializing a `CreateSchedule`,
    # and the API reorganizes the post data as a table-based ORM object, so
    # we just need to make sure we send the templates with the post_data
    post_data = schedule.model_dump(exclude={"id"})
    post_data["templates"] = [
        template.model_dump(exclude_none=True, exclude_unset=True) for template in schedule.templates
    ]

    async with CLIENT_FACTORY.aclient() as client:
        r = await client.post("/schedules", json=post_data)
        r.raise_for_status()

    return True


async def delete_schedule(schedule_id: str | UUID) -> None:
    """DELETEs a schedule by ID using the REST API. This is a cascading delete
    that will remove all the schedule's template manifests but will not affect
    any campaigns created from this schedule in the past.
    """
    actor = app.storage.client["state"].user.username

    async with CLIENT_FACTORY.aclient() as client:
        client.headers["X-Auth-Request-User"] = actor
        r = await client.delete(f"/schedules/{schedule_id}")
        r.raise_for_status()


async def oneshot_schedule(schedule_id: str | UUID) -> None:
    """Creates a one-shot execution of a schedule using the REST API."""
    async with CLIENT_FACTORY.aclient() as client:
        r = await client.post(f"/schedules/{schedule_id}/oneshot")
        r.raise_for_status()


async def put_schedule_template(
    schedule_id: str | UUID, template_id: str | UUID, manifest: dict | CreateManifestTemplate
) -> None:
    """PUTs a new manifest to the API for a given template. This will replace
    the content of the template.
    """
    actor = app.storage.client["state"].user.username

    if isinstance(manifest, CreateManifestTemplate):
        template = manifest.model_dump(mode="json", exclude_none=True, exclude_unset=True)

    async with CLIENT_FACTORY.aclient() as client:
        client.headers["X-Auth-Request-User"] = actor
        r = await client.put(
            f"/schedules/{schedule_id}/templates/{template_id}",
            json=template,
        )
        r.raise_for_status()
