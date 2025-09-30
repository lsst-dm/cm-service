import asyncio
from collections.abc import AsyncGenerator, Sequence
from functools import partial

from httpx import AsyncClient
from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from lsst.cmservice.common.enums import DEFAULT_NAMESPACE

from ..lib.client_factory import CLIENT_FACTORY
from ..lib.configedit import configuration_edit
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


async def compile_campaign_manifests(id: str, manifests: list[dict]) -> None:
    """Renders a row or table of campaign manifest cards, substituting library
    manifests for any mandatory manifests not present in the campaign.
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
                manifests.append(manifest_.json())
    with ui.row():
        for manifest in manifests:
            with ui.card():
                with ui.card_section():
                    ui.label(manifest["kind"].upper()).classes("text-subtitle1")
                    ui.label(manifest["name"]).classes("text-subtitle2")
                with ui.card_actions().props("align=right").classes("items-center text-sm w-full"):
                    ui.chip(
                        manifest["version"],
                        icon="commit",
                        color="white",
                    ).tooltip("Manifest Version")
                    ui.button(
                        icon="content_paste_go",
                        color="dark",
                    ).props("style: flat").tooltip("Apply Manifest")
                    ui.button(
                        icon="edit",
                        color="dark",
                        on_click=partial(configuration_edit, manifest_id=manifest["id"], namespace=id),
                    ).props("style: flat").tooltip("Edit Manifest Configuration")


async def toggle_campaign_state(e: ValueChangeEventArguments, campaign: dict) -> None:
    """Toggles a campaign between the PAUSED and RUNNING states by affecting
    a PATCH call to the campaign API.
    """
    campaign_name = campaign["name"]
    campaign_id = campaign["id"]
    n = ui.notification(timeout=None)

    patch_data: dict[str, str]
    if e.value:
        toggle_action = "start"
        n.message = f"Starting campaign {campaign_name}"
        patch_data = {"status": "running"}
    else:
        toggle_action = "pause"
        n.message = f"Pausing campaign {campaign_name}"
        patch_data = {"status": "paused"}

    async with CLIENT_FACTORY.aclient() as aclient:
        r = await aclient.patch(
            f"/campaigns/{campaign_id}",
            json=patch_data,
            headers={"Content-Type": "application/merge-patch+json"},
        )
        r.raise_for_status()
        status_url = r.headers["StatusUpdate"]

        activity_log: list = []
        for _ in range(10):
            n.spinner = True
            r = await aclient.get(status_url)
            if r.is_success:
                activity_log.extend(r.json())
                if len(activity_log):
                    break
            await asyncio.sleep(1.0)

    error = r.is_error or activity_log[0].get("detail", {}).get("error", None)
    n.spinner = False
    if error:
        n.color = "negative"
        message = f"Failed to {toggle_action} {campaign_name}: {error}"
        n.message = message
        n.close_button = True
    else:
        n.color = "positive"
        n.message = f"{toggle_action} {campaign_name}"
        n.timeout = 3.0
