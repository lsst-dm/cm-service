from __future__ import annotations

from nicegui import ui
from yaml import dump

from .. import api
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import StatusDecorators
from ..lib.timestamp import iso_timestamp
from .common import cm_frame


async def configuration_history(id: str) -> list[dict]:
    data = []
    # get latest version of node
    async with CLIENT_FACTORY.aclient() as session:
        r = await session.head(f"/nodes/{id}")
        latest = int(r.headers["Latest"])
        namespace = r.headers["Namespace"]
        name = r.headers["Name"]
        for v in range(1, latest + 1):
            n = await session.get(f"/nodes/{name}?campaign-id={namespace}&version={v}")
            n.raise_for_status()
            data.append(n.json()["configuration"])
    return data


async def node_activity_logs(id: str) -> list[dict]:
    # FIXME this API needs to be sorted by `finished_at`
    async with CLIENT_FACTORY.aclient() as session:
        r = await session.get(f"/logs?node={id}")
        r.raise_for_status()
    return r.json()


@ui.refreshable
async def node_config_history_carousel(node: dict) -> None:
    """Builds a carousel ui element providing a browsable history of Node
    configuration versions.
    """
    id = node["id"]
    with ui.row().classes("w-full justify-center"):
        with (
            ui.carousel(animated=True, arrows=True, navigation=False)
            .classes("justify-center")
            .props("control-color=black")
        ):
            for i, config in enumerate(await configuration_history(id)):
                with ui.carousel_slide().classes("w-full justify-center"):
                    with ui.card().classes("justify-center"):
                        ui.label(f"Configuration Version {i + 1}").classes("text-subtitle1")
                        code = ui.code(dump(config), language="yaml")
                        code.copy_button.delete()


@ui.refreshable
async def node_activity_timeline(node: dict) -> None:
    """Builds a timeline ui element providing an illustration of Node status
    changes over time, including error messages when available.
    """
    id = node["id"]
    name = node["name"]
    with ui.timeline(side="right").classes("w-full"):
        entry_milestone = ""
        for entry in await node_activity_logs(id):
            if entry_body := entry["detail"].get("error", ""):
                entry_title = f"{name} failed to {entry['detail']['trigger']}"
                entry_color = "negative"
            elif entry_milestone := entry["metadata"].get("milestone", ""):
                entry_title = f"Milestone {entry_milestone} Reached"
                entry_color = "secondary"
            else:
                entry_body = entry["detail"].get("message", "")
                entry_title = f"{name} became {entry['to_status']}"
                entry_color = "primary"

                match entry["to_status"]:
                    case "ready":
                        artifact_path = node["metadata"].get("artifact_path", None)
                        entry_body += artifact_path or ""
                    case "running":
                        job_id = node["metadata"].get("launcher", {}).get("job_id", "Unknown")
                        execute_host = node["metadata"].get("launcher", {}).get("execute_host", "Unknown")
                        entry_body += f"Job {job_id} on launch host {execute_host}"
                    case _:
                        ...

            with ui.timeline_entry(
                body=entry_body,
                title=entry_title,
                subtitle=entry["finished_at"],
                icon=StatusDecorators[entry["to_status"]].emoji,
                color=entry_color,
            ):
                if entry_milestone:
                    ui.code(dump(entry["detail"]), language="yaml")

        ui.timeline_entry(
            "",
            title=f"{name} Created",
            subtitle=iso_timestamp(node["metadata"]["crtime"]),
            icon=StatusDecorators.waiting.emoji,
        )


async def node_metadata_display(node: dict) -> None:
    """Displays a Node's metadata dictionary as a YAML document in a syntax-
    highlighted Code widget.
    """
    node_metadata = dump(node["metadata"])
    ui.code(content=node_metadata, language="yaml").classes("w-full")


@ui.page("/node/{id}")
async def node_detail(id: str) -> None:
    """Builds a Node Detail ui page."""
    data = await api.describe_one_node(id=id)
    node = data["node"]
    node_status = StatusDecorators[node["status"]]
    with cm_frame("Node Detail", [node["name"]], footers=[node["id"]]):
        with ui.row():
            with ui.link(target=f"/campaign/{node['namespace']}"):
                ui.chip("Campaign", icon="shape_line", color="white").tooltip(node["namespace"])
            ui.chip(node["kind"], icon="fingerprint", color="white").tooltip("Node Kind")
            ui.chip(node["version"], icon="commit", color="white").tooltip("Node Version")
            ui.chip(node["status"], icon=node_status.emoji, color=node_status.hex).tooltip("Node Status")
            if node["status"] == "failed":
                ui.chip("retry", icon="restart_alt", color="accent").tooltip("Retry a Failed Node")
        ui.separator()

        with ui.tabs().classes("items-center w-full") as tabs:
            timeline_tab = ui.tab("Timeline")
            config_tab = ui.tab("Configuration")
            metadata_tab = ui.tab("Metadata")

        with ui.tab_panels(tabs, value=timeline_tab).classes("w-full"):
            with ui.tab_panel(timeline_tab):
                await node_activity_timeline(node)
            with ui.tab_panel(config_tab):
                await node_config_history_carousel(node)
            with ui.tab_panel(metadata_tab):
                await node_metadata_display(node)
