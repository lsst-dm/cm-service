import asyncio
from collections.abc import AsyncGenerator, Sequence
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

from httpx import AsyncClient
from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments

from lsst.cmservice.models.enums import DEFAULT_NAMESPACE

from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import MANIFEST_KIND_ICONS
from ..lib.models import KIND_TO_SPEC
from .manifests import get_one_manifest


async def get_campaign_summary(client: AsyncClient) -> AsyncGenerator[dict]:
    """Generates a summary dictionary for all campaigns known to the API."""
    r = await client.get("/campaigns")
    r.raise_for_status()
    campaigns: Sequence[dict] = r.json()
    for campaign in campaigns:
        campaign_id = campaign.get("id")
        summary = await client.get(f"/campaigns/{campaign_id}/summary")
        summary.raise_for_status()
        if summary.status_code == 204:
            continue
        yield summary.json()


async def describe_one_campaign(id: str, client: AsyncClient) -> dict:
    """Builds a detailed campaign dictionary by assembling multiple API calls
    for a single campaign.
    """
    r = await client.get(f"/campaigns/{id}")
    r.raise_for_status()
    campaign_detail = {"campaign": r.json()}

    campaign_detail["nodes"] = []
    n = await client.get(r.headers["Nodes"])
    n.raise_for_status()
    nodes = n.json()
    while nodes:
        campaign_detail["nodes"].extend(nodes)
        n = await client.get(n.headers["Next"])
        n.raise_for_status()
        nodes = n.json()

    m = await client.get(r.headers["Manifests"])
    m.raise_for_status()
    campaign_detail["manifests"] = m.json()

    g = await client.get(f"/campaigns/{id}/graph")
    g.raise_for_status()
    campaign_detail["graph"] = g.json()

    a = await client.get(f"/campaigns/{id}/logs")
    a.raise_for_status()
    campaign_detail["logs"] = a.json()

    return campaign_detail


async def get_campaign_manifests(id: str | None = None, manifests: list[dict] = []) -> list[dict]:
    """API helper for fetching a collection of campaign or library manifests.
    Parameters
    ----------
    id : str | None
        The ID of a campaign whose manifests to fetch. If the `id` is `None`,
        then the library manifests will be fetched instead.
    """
    # -- if the campaign does not have these kinds, then we will pull the
    #    version 0 of that kind from the library (default namespace)
    mandatory_kinds = ["lsst", "bps", "butler", "wms", "site"]

    for kind in mandatory_kinds:
        if not list(filter(lambda m: m["kind"] == kind, manifests)):
            manifest_ = await get_one_manifest(
                namespace=str(DEFAULT_NAMESPACE), kind=kind, name=None, version=None
            )
            if manifest_ is not None:
                # Round trip through the pydantic model
                manifest_spec = manifest_.json()
                manifest_model = KIND_TO_SPEC[manifest_spec["kind"]].model_validate(
                    manifest_spec["spec"], extra="ignore"
                )
                manifest_spec["spec"] = manifest_model.model_dump(exclude_none=True, exclude_unset=True)
                manifests.append(manifest_spec)

    return manifests


async def compile_campaign_manifests(campaign_id: str | None = None, manifests: list[dict] = []) -> None:
    """Renders a row or table of campaign manifest cards, substituting library
    manifests for any mandatory manifests not present in the campaign.

    If called without arguments, this function will compile a row of Library
    manifests.
    """
    # FIXME the configuration chain lookup does not substitute a campaign
    # manifest for a library manifest; the library manifest is always in the
    # chain map if it exists, so it's not correct to "hide" library manifests
    # from the user in the campaign detail.
    # FIXME in future label selection of manifests will complicate the "view"
    # of a set of manifests relevant to the campaign, since the selectors will
    # differ at the node level.
    # FIXME this is a bad pattern because it mixes ui elements with data ops

    manifests = await get_campaign_manifests(campaign_id, manifests)

    with ui.row():
        for manifest in manifests:
            with ui.card():
                with ui.card_section():
                    ui.label(manifest["name"]).classes("text-subtitle2")
                with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                    ui.chip(text=manifest["kind"].upper(), color="accent").classes("text-xs").props(
                        "outline square"
                    ).bind_icon_from(MANIFEST_KIND_ICONS, manifest["kind"])
                    ui.chip(
                        manifest["version"],
                        icon="commit",
                        color="white",
                    ).tooltip("Manifest Version")
                    ui.button(
                        icon="preview" if campaign_id is None else "edit",
                        color="dark",
                    ).props("style: flat").tooltip("Edit Manifest Configuration")


async def toggle_campaign_state(e: ValueChangeEventArguments | SimpleNamespace, campaign: dict) -> None:
    """Toggles a campaign between the PAUSED and RUNNING states by affecting
    a PATCH call to the campaign API.

    Parameters
    ----------
    e: ValueChangeEventArguments | SimpleNamespace
        When called by a NiceGUI element (e.g., `ui.switch`), we receive the
        event associated with an action. Alternately, a `SimpleNamespace` can
        approximate the event as long as the correct attribute is set.
    """
    if TYPE_CHECKING:
        e = cast(ValueChangeEventArguments, e)
    update_complete = asyncio.Event()
    campaign_name = campaign.get("name", "")
    campaign_id = campaign["id"]
    n = ui.notification(timeout=None)

    if e.value:
        n.message = f"Starting campaign {campaign_name}"
        new_status = "running"
    else:
        n.message = f"Pausing campaign {campaign_name}"
        new_status = "paused"

    async with CLIENT_FACTORY.aclient() as aclient:
        r = await aclient.get(f"/campaigns/{campaign_id}")
        r.raise_for_status()
        current_status = r.json()["status"]
        status_url: str | None = None
        is_error = False
        error_str = ""

        # Fail fast if this is going to be a no-op
        if current_status == new_status:
            update_complete.set()
        else:
            r = await aclient.patch(
                f"/campaigns/{campaign_id}",
                json={"status": new_status},
                headers={"Content-Type": "application/merge-patch+json"},
            )
            r.raise_for_status()
            status_url = r.headers.get("StatusUpdate", None)

        activity_log: list = []
        for _ in range(10):
            n.spinner = True
            if update_complete.is_set():
                break
            elif not status_url:
                is_error = True
                error_str = "No status update URL received."
                break
            r = await aclient.get(status_url)
            if r.is_success:
                activity_log.extend(r.json())
                if len(activity_log):
                    update_complete.set()
            is_error = r.is_error
            await asyncio.sleep(1.0)

        if activity_log:
            is_error = activity_log[0].get("detail", {}).get("error", None)

    n.spinner = False
    if is_error:
        n.color = "negative"
        message = f"Failed to set {campaign_name} to {new_status}: {error_str}"
        n.message = message
        n.close_button = True
    else:
        app.storage.client["state"].campaigns[campaign_id]["status"] = new_status
        n.color = "positive"
        n.message = f"{campaign_name} is now {new_status}"
        n.position = "top"
        n.close_button = "OK"
        n.close_button = True
