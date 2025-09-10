from __future__ import annotations

from nicegui import run, ui
from yaml import dump

from .. import api
from ..lib.client import http_client
from ..lib.enum import StatusDecorators
from ..lib.timestamp import iso_timestamp
from .common import cm_frame


def configuration_history(id: str) -> list[dict]:
    data = []
    # get latest version of node
    with http_client() as session:
        r = session.head(f"/nodes/{id}")
        latest = int(r.headers["Latest"])
        namespace = r.headers["Namespace"]
        name = r.headers["Name"]
        for v in range(1, latest + 1):
            n = session.get(f"/nodes/{name}?campaign-id={namespace}&version={v}")
            n.raise_for_status()
            data.append(n.json()["configuration"])
    return data


def node_activity_logs(id: str) -> list[dict]:
    with http_client() as session:
        r = session.get(f"/logs?node={id}")
        r.raise_for_status()
    return r.json()


@ui.refreshable
def node_config_history_carousel(node: dict) -> None:
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
            for i, config in enumerate(configuration_history(id)):
                with ui.carousel_slide().classes("w-full justify-center"):
                    with ui.card().classes("justify-center"):
                        ui.label(f"Configuration Version {i + 1}").classes("text-subtitle1")
                        code = ui.code(dump(config), language="yaml")
                        code.copy_button.delete()


@ui.refreshable
def node_activity_timeline(node: dict) -> None:
    """Builds a timeline ui element providing an illustration of Node status
    changes over time, including error messages when available.
    """
    id = node["id"]
    name = node["name"]
    with ui.timeline(side="right").classes("w-full"):
        for entry in node_activity_logs(id):
            if entry_body := entry["detail"].get("error", ""):
                entry_title = f"{name} failed to {entry['detail']['trigger']}"
                entry_color = "negative"
            else:
                entry_body = entry["detail"].get("message", "")
                entry_title = f"{name} became {entry['to_status']}"
                entry_color = "primary"

            ui.timeline_entry(
                body=entry_body,
                title=entry_title,
                subtitle=entry["finished_at"],
                icon=StatusDecorators[entry["to_status"]].emoji,
                color=entry_color,
            )
        ui.timeline_entry(
            "",
            title=f"{name} Created",
            subtitle=iso_timestamp(node["metadata"]["crtime"]),
            icon=StatusDecorators.waiting.emoji,
        )


@ui.page("/node/{id}")
async def node_detail(id: str) -> None:
    """Builds a Node Detail ui page."""
    data = await run.io_bound(api.describe_one_node, id=id)
    node = data["node"]
    node_status = StatusDecorators[node["status"]]
    with cm_frame("Node Detail", [node["name"]], footers=[node["id"]]):
        with ui.row():
            with ui.link(target=f"/campaign/{node['namespace']}"):
                ui.chip("Campaign", icon="shape_line", color="white").tooltip(node["namespace"])
            ui.chip(node["version"], icon="commit", color="white").tooltip("Node Version")
            ui.chip(node["status"], icon=node_status.emoji, color=node_status.hex).tooltip("Node Status")
            if node["status"] == "failed":
                ui.chip("retry", icon="restart_alt", color="accent").tooltip("Retry a Failed Node")
        ui.separator()

        with ui.tabs().classes("items-center w-full") as tabs:
            timeline_tab = ui.tab("Timeline")
            config_tab = ui.tab("Configuration")

        with ui.tab_panels(tabs, value=timeline_tab).classes("w-full"):
            with ui.tab_panel(timeline_tab):
                node_activity_timeline(node)
            with ui.tab_panel(config_tab):
                node_config_history_carousel(node)
