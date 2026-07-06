"""Library module for supporting functions related to the schedules cli
command.
"""

from pathlib import Path

import yaml
from httpx import HTTPStatusError, Response
from pydantic_extra_types.cron import CronStr
from rich.console import Console

from lsst.cmservice.models.db.schedules import CreateManifestTemplate, CreateSchedule

from ..client import http_client
from ..models import TypedContext

console = Console()


def create_schedule(spec: dict | None) -> CreateSchedule:
    """Create a new schedule object and apply the provided configuration spec
    to it.
    """
    schedule = CreateSchedule(
        name="",
        cron=CronStr("* * * * *"),
        metadata_={
            "owner": "nobody",
        },
        configuration={},
        is_enabled=False,
        templates=[],
    )
    if spec is not None:
        schedule.configuration = spec
    return schedule


def read_schedule_from_file(filename: Path) -> list[dict]:
    """Read a schedule specification from a YAML file and return the list of
    manifests.
    """
    contents = filename.read_text()
    manifest_list = list(yaml.safe_load_all(contents))
    return manifest_list


def apply_templates_to_schedule(schedule: CreateSchedule, templates: dict[str, dict]) -> CreateSchedule:
    """Apply the provided collection of manifest templates to a schedule."""
    for k, manifest in templates.items():
        schedule.templates.append(
            CreateManifestTemplate(
                name=k,
                kind=manifest["kind"],
                manifest=yaml.safe_dump(manifest, explicit_start=True),
            )
        )

    return schedule


def post_new_schedule(ctx: TypedContext, schedule: CreateSchedule) -> Response | None:
    """Post a new schedule to the CMService API."""
    post_data = schedule.model_dump(exclude={"id"})
    post_data["templates"] = [
        template.model_dump(exclude_none=True, exclude_unset=True) for template in schedule.templates
    ]

    r = None
    with http_client(ctx) as client:
        try:
            r = client.post("/schedules", json=post_data)
            r.raise_for_status()
        except HTTPStatusError as e:
            console.print(e.response.reason_phrase)
    return r
