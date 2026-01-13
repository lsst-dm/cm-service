from __future__ import annotations

from functools import partial
from typing import Any, Self, TypedDict

from httpx import AsyncClient
from nicegui import app, ui
from yaml import dump

from .. import api
from ..components import dialog, storage, strings
from ..lib.client_factory import CLIENT_FACTORY
from ..lib.enum import StatusDecorators
from ..lib.timestamp import iso_timestamp
from .common import CMPage


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


# TODO replace with a pydantic model
class NodeDetailPageModel(TypedDict):
    node: dict[str, Any]
    logs: list


class NodeDetailPage(CMPage[NodeDetailPageModel]):
    """..."""

    def drawer_contents(self) -> None: ...

    async def setup(self, client_: AsyncClient | None = None, *, node_id: str = "") -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        if client_ is None:
            raise RuntimeError("Node Detail page setup requires an httpx client")

        self.show_spinner()
        storage.initialize_client_storage()
        data = await api.describe_one_node(id=node_id)
        self.node_id = node_id

        self.model: NodeDetailPageModel = {
            "node": data["node"],
            "logs": data["logs"],
        }

        with self.footer:
            ui.label().classes("text-xs").bind_text_from(self, "node_id", strict=False)

        self.breadcrumbs.append(data["node"]["name"])
        self.create_header.refresh()
        return self

    async def render(self) -> None:
        """Method to create main content for page.

        Subclasses should use the `create_content()` method, which is called
        from within the content column's context manager.
        """
        with self.content:
            await self.create_content()

    async def node_detail_ribbon(self) -> None:
        """Renders a Node Detail ribbon.

        The Node Detail Ribbon includes a link back to the campaign, chips
        for kind and status, as well as transport controls including recovery
        and step-advance buttons if available.
        """
        node = self.model["node"]
        with ui.row():
            with ui.link(target=f"/campaign/{node['namespace']}"):
                ui.chip("Campaign", icon="shape_line", color="white").tooltip(node["namespace"])
            ui.chip(node["kind"], icon="fingerprint", color="white").tooltip("Node Kind")
            ui.chip(node["version"], icon="commit", color="white").tooltip("Node Version")
            await self.node_status_chip()
            if node["status"] == "failed":
                ui.chip("recover", icon="healing", color="accent").tooltip(
                    strings.NODE_RECOVERY_DIALOG_LABEL
                ).props("clickable").on(
                    "click", lambda e: dialog.NodeRecoveryPopup.click(e, node, self.create_content)
                )
            if all([node["kind"] == "breakpoint", node["status"] != "failed"]):
                # TODO this could be an expanding FAB
                await self.breakpoint_accept_chip()
                await self.breakpoint_reject_chip()
            else:
                # if campaign is paused, then show transport (step) control
                await self.node_advance_chip()

    async def node_tab_bar(self) -> None:
        """Renders a tab bar for the node detail page.

        The tab bar and the tabs are created as page instance attributes.
        """
        with ui.tabs().classes("items-center w-full") as self.tabs:
            self.timeline_tab = ui.tab("Timeline")
            self.config_tab = ui.tab("Configuration")
            self.metadata_tab = ui.tab("Metadata")

    async def node_tab_panels(self) -> None:
        with ui.tab_panels(self.tabs, value=self.timeline_tab).classes("w-full"):
            with ui.tab_panel(self.timeline_tab):
                await self.node_activity_timeline()
            with ui.tab_panel(self.config_tab):
                await self.node_config_history_carousel()
            with ui.tab_panel(self.metadata_tab):
                await self.node_metadata_display()

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """
        self.show_spinner()
        await self.node_detail_ribbon()
        ui.separator()
        await self.node_tab_bar()
        await self.node_tab_panels()

        self.hide_spinner()

    @ui.refreshable_method
    async def node_status_chip(self) -> None:
        """Renders a chip indicating the Status of the Node."""
        data = await api.describe_one_node(id=self.node_id)
        self.model["node"] = data["node"]
        node_status = StatusDecorators[data["node"]["status"]]
        status, _ = ui.state(data["node"]["status"])
        icon, _ = ui.state(node_status.emoji)
        color, _ = ui.state(node_status.hex)

        # For a breakpoint node, we will show the chip only if it is accepted
        if self.model["node"]["kind"] != "breakpoint":
            ui.chip(status, icon=icon, color=color).tooltip("Node Status")
        else:
            ui.chip(status, icon=icon, color=color).tooltip("Node Status").bind_visibility_from(
                target_object=self.model["node"],
                target_name="status",
                backward=lambda v: v in ["accepted", "failed"],
            )

    @ui.refreshable_method
    async def node_activity_timeline(self) -> None:
        """Builds a timeline providing an illustration of Node status changes
        and milestones over time, including error messages when available.
        """
        id = self.model["node"]["id"]
        name = self.model["node"]["name"]
        metadata = self.model["node"]["metadata"]
        with ui.timeline(side="right").classes("w-full"):
            entry_milestone = ""
            for entry in await api.node_activity_logs(id):
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
                            artifact_path = metadata.get("artifact_path", None)
                            entry_body += artifact_path or ""
                        case "running":
                            job_id = metadata.get("launcher", {}).get("job_id", "Unknown")
                            execute_host = metadata.get("launcher", {}).get("execute_host", "Unknown")
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
                subtitle=iso_timestamp(metadata["crtime"]),
                icon=StatusDecorators.waiting.emoji,
            )

    @ui.refreshable_method
    async def node_config_history_carousel(self) -> None:
        """Builds a carousel ui element providing a browsable history of Node
        configuration versions.
        """
        id = self.model["node"]["id"]
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

    @ui.refreshable_method
    async def node_metadata_display(self) -> None:
        """Displays a Node's metadata dictionary as a YAML document in a
        syntax-highlighted Code widget.
        """
        node_metadata = dump(self.model["node"]["metadata"])
        ui.code(content=node_metadata, language="yaml").classes("w-full")

    async def node_advance_chip(self) -> None:
        """Adds a chip as a state-advance button for the Node.

        This control is only visible if the associated Campaign is Paused, and
        is disabled if the Node is already in a terminal state.
        """
        node_id = self.node_id
        node = self.model["node"]
        campaign_id = self.model["node"]["namespace"]
        icon = node["icon"] = node.get("icon", "fast_forward")
        label = node["label"] = node.get("label", "")
        fast_forward = partial(api.fast_forward_node, n0=node_id)
        ui.chip(label, icon=icon, color="white", on_click=fast_forward).tooltip(
            "Step Forward"
        ).bind_icon_from(node, "icon").bind_text_from(node, "label").bind_visibility_from(
            app.storage.client["state"].campaigns[campaign_id], target_name="status", value="paused"
        ).bind_enabled_from(node, target_name="status", backward=lambda x: x not in ("failed", "accepted"))

    async def breakpoint_accept_chip(self) -> None:
        """Adds a chip as an Accept button for a Breakpoint Node.

        This control is only visible if the Node is a breakpoint kind.
        """
        if all(
            [
                self.model["node"]["kind"] == "breakpoint",
                self.model["node"]["status"] != "accepted",
            ]
        ):
            force_method = partial(api.retry_restart_node, n0=self.node_id, force=True, accept=True)
            ui.chip(
                "accept",
                icon="recommend",
                color="positive",
                on_click=force_method,
            ).tooltip(strings.BREAKPOINT_ACCEPT_TOOLTIP)
            # TODO refresh element(s) in click callback!

    async def breakpoint_reject_chip(self) -> None:
        """Adds a chip as an Reject button for a Breakpoint Node.

        This control is only visible if the Node is a breakpoint kind.
        """
        if all(
            [
                self.model["node"]["kind"] == "breakpoint",
                self.model["node"]["status"] != "accepted",
            ]
        ):
            force_method = partial(api.retry_restart_node, n0=self.node_id, force=True, reject=True)
            ui.chip(
                "reject",
                icon="thumb_down",
                color="negative",
                on_click=force_method,
            ).tooltip(strings.BREAKPOINT_REJECT_TOOLTIP)
            # TODO refresh element(s) in click callback!
