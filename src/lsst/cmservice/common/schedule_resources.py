"""Module for functions dealing with a Schedule's external resource.

A Schedule with a ``uri`` in its configuration loads its campaign templates
from the external resource identified by that URI. If the resource also
includes a ``schedule`` manifest, that manifest is the authority on the
Schedule's configuration: when the Schedule is refreshed from its resource, the
schedule manifest's spec *replaces* the Schedule's configuration and cron. If
the resource does not include a ``schedule`` manifest, the Schedule's
configuration is managed by CM and is not changed by a refresh.

A Schedule is refreshed from its resource when the Schedule is created with a
``uri`` (or given a new one), whenever the Schedule runs, and on request via
the schedule refresh API. There is no other, automatic, refresh.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import httpx2
import yaml
from pydantic import ValidationError
from pydantic_extra_types.cron import CronStr

from lsst.cmservice.models.api.schedules import ScheduleConfiguration
from lsst.cmservice.models.db.audit import AuditLog
from lsst.cmservice.models.db.schedules import CreateManifestTemplate, Schedule, check_schedule_configuration
from lsst.cmservice.models.enums import AuditActionEnum, ManifestKind
from lsst.cmservice.models.lib.resources import Resource


class ScheduleResourceError(Exception):
    """Raised when a Schedule's external resource cannot be fetched, parsed,
    or applied to the Schedule.
    """


@dataclass
class ScheduleResource:
    """The contents of a Schedule's external resource."""

    templates: list[CreateManifestTemplate] = field(default_factory=list)
    """The campaign manifest templates in the resource."""

    schedule_spec: dict | None = None
    """The spec of the resource's schedule manifest, if it has one."""


async def fetch_schedule_resource(uri: str) -> ScheduleResource:
    """Fetches and parses a Schedule's external resource.

    The resource must be a YAML file of one or more manifest documents, of
    which at most one may be a ``schedule`` manifest.

    Raises
    ------
    ScheduleResourceError
        If the resource cannot be fetched or is not a valid collection of
        manifests.
    """
    # TODO this assumes and only supports YAML files, which would implicitly
    # support JSON files as well except it'd be parsed as a single document
    # with a list of dicts `[[{...}, {...}]]`
    async with Resource.http_async_client() as aclient:
        try:
            response = await aclient.get(uri)
            response.raise_for_status()
        except httpx2.HTTPError as e:
            msg = f"Could not fetch schedule resource {uri}: {e}"
            raise ScheduleResourceError(msg) from e

    resource = ScheduleResource()
    try:
        for manifest in yaml.safe_load_all(response.content):
            if manifest is None:
                continue
            if manifest["kind"] == ManifestKind.schedule.name:
                if resource.schedule_spec is not None:
                    msg = f"Schedule resource {uri} has more than one schedule manifest"
                    raise ScheduleResourceError(msg)
                resource.schedule_spec = manifest.get("spec") or {}
                continue
            resource.templates.append(
                CreateManifestTemplate(
                    name=manifest["metadata"].get("name", uuid4().hex[:8]),
                    kind=manifest["kind"],
                    manifest=yaml.safe_dump(manifest, explicit_start=True),
                )
            )
    except (yaml.YAMLError, KeyError, TypeError, AttributeError, ValidationError) as e:
        msg = f"Schedule resource {uri} is not a valid collection of manifests: {e}"
        raise ScheduleResourceError(msg) from e
    return resource


def apply_schedule_spec(schedule: Schedule, spec: dict) -> dict[str, dict[str, Any]]:
    """Replaces a Schedule's configuration and cron with those from the spec
    of a resource's schedule manifest.

    The spec's ``cron`` becomes the Schedule's cron, or the default cron if
    the spec has none. The rest of the spec, which is validated as a schedule
    configuration, becomes the Schedule's configuration, with only the fields
    the spec sets; any other configuration field reads as its default. The
    Schedule's ``uri`` is kept, and is never changed by the spec.

    Returns
    -------
    dict[str, dict[str, Any]]
        A mapping of each changed field name to its ``from`` and ``to``
        values, which is empty if nothing changed. The ``cron`` field refers to
        the Schedule's cron, and other names to its configuration fields.

    Raises
    ------
    ScheduleResourceError
        If the spec is not a valid schedule configuration, or includes any of
        the Schedule's own fields other than its cron.
    """
    spec = dict(spec)
    spec.pop("uri", None)
    if (uri := schedule.configuration.get("uri")) is not None:
        spec["uri"] = uri
    try:
        cron = CronStr(spec.pop("cron", ScheduleConfiguration.model_fields["cron"].default))
        check_schedule_configuration(spec)
        configuration = ScheduleConfiguration.model_validate(spec).model_dump(exclude_unset=True)
    except (ValidationError, ValueError, TypeError) as e:
        msg = f"Schedule resource has an invalid schedule manifest: {e}"
        raise ScheduleResourceError(msg) from e

    changes = {
        name: {"from": schedule.configuration.get(name), "to": configuration.get(name)}
        for name in configuration.keys() | schedule.configuration.keys()
        if name != "cron" and schedule.configuration.get(name) != configuration.get(name)
    }
    if str(schedule.cron) != str(cron):
        changes["cron"] = {"from": str(schedule.cron), "to": str(cron)}

    if changes:
        schedule.configuration = configuration
        schedule.cron = cron
        if schedule.is_enabled:
            schedule.next_run_at = cron.next_run  # type: ignore[assignment]
    return changes


async def refresh_schedule(schedule: Schedule) -> tuple[ScheduleResource | None, dict[str, dict[str, Any]]]:
    """Refreshes a Schedule from its external resource, if it has one.

    Returns
    -------
    tuple[ScheduleResource | None, dict[str, dict[str, Any]]]
        The fetched resource, or None if the Schedule has no external
        resource, and the changes made to the Schedule (see
        `apply_schedule_spec`).

    Raises
    ------
    ScheduleResourceError
        If the resource cannot be fetched, parsed, or applied.
    """
    if (uri := schedule.configuration.get("uri")) is None:
        return None, {}
    resource = await fetch_schedule_resource(uri)
    if resource.schedule_spec is None:
        return resource, {}
    return resource, apply_schedule_spec(schedule, resource.schedule_spec)


def refresh_audit_log(
    schedule: Schedule, changes: dict[str, dict[str, Any]], *, actor: str, request_id: UUID
) -> AuditLog:
    """Returns an audit log entry for changes made to a Schedule by a refresh
    from its external resource.
    """
    return AuditLog(
        actor=actor,
        action=AuditActionEnum.update,
        request_id=request_id,
        object_id=schedule.id,
        object_type=ManifestKind.schedule,
        object_name=schedule.name,
        context={"uri": schedule.configuration.get("uri"), "changes": changes},
    )
