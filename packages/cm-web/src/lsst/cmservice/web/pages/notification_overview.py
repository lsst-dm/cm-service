from typing import TYPE_CHECKING, Any, Literal, Self, assert_never

from httpx import AsyncClient
from nice_dialogs.dialogs import ConfirmationDialog
from nicegui import ui
from nicegui.events import ClickEventArguments, GenericEventArguments

from lsst.cmservice.models.api.notifications import NotificationLabelManifest

from ..api import notifications
from ..components.dialog import NewNotificationLabelDialog
from .common import CMPage, CMPageModel


class NotificationOverviewPageModel(CMPageModel): ...


class NotificationOverviewPage(CMPage[NotificationOverviewPageModel]):
    """Display currently configured CM Notification Channels in a table layout
    with optional filtering and contextual action buttons.
    """

    async def setup(self, client_: AsyncClient | None = None) -> Self:
        """Async method called at page creation. Subpages can override this
        method to perform data loading/prep, etc., before calling render().
        """
        self.show_spinner()
        self.model: NotificationOverviewPageModel = {}
        return self

    def drawer_contents(self) -> None:
        """Right-side drawer contents, mostly filter options for the schedules
        table.
        """
        # TODO filter by kind
        ...

    @ui.refreshable_method
    async def create_content(self) -> None:
        """The primary content-rendering method for the page, called by render
        within the column element between page header and footer.
        """

        self.table_content = ui.element("div").classes(
            "w-full h-full pt-[0.5rem] pb-[0.5rem] overflow-y-auto"
        )
        await self.create_notifications_table()
        with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
            ui.button(icon="add", on_click=self.handle_new_notification).props("fab color=accent")
        self.hide_spinner()

    @ui.refreshable_method
    async def create_notifications_table(self) -> None:
        """Render a table of notification labels"""
        self.table_content.clear()

        columns: list[dict[str, Any]] = [
            {
                "name": "name",
                "label": "Name",
                "field": "name",
                "sortable": True,
                ":classes": "(row) => row.classes",
            },
            {
                "name": "kind",
                "label": "Kind",
                "field": "kind",
                "sortable": True,
                ":classes": "(row) => row.classes",
            },
            {"name": "actions", "label": "Actions", "field": "actions"},
        ]
        with self.table_content:
            self.notifications_table = ui.table(columns=columns, rows=[], row_key="name").classes(
                "w-full h-full overflow-auto"
            )
        await self.update_table_rows()
        with self.notifications_table.add_slot("body-cell-actions"):
            with self.notifications_table.cell("actions"):
                await self.get_table_actions()

    def apply_row_filter(self, label: dict) -> bool:
        """Compare label to active page filters"""
        # TODO
        return True

    async def update_table_rows(self) -> None:
        """Replace the page table's rows with a new set."""
        self.notifications_table.rows = [
            {
                "name": label["name"],
                "kind": label["kind"],
                "secret": "********" if label.get("secret") else "",
                "filters": label["configuration"].get("filters", []),
                "actions": None,
                "classes": "",
            }
            async for label in notifications.get_notifications()
            if self.apply_row_filter(label)
        ]
        self.table_index = {row["name"]: row for row in self.notifications_table.rows}

    async def get_table_actions(self) -> None:
        """Create action buttons for a table cell"""
        ui.button(
            icon="edit_notifications",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.name, 'rules')",
            handler=self.handle_row_action,
        ).tooltip("Notification Rules")
        ui.button(
            icon="copy_all",
            color="dark",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.name, 'clone')",
            handler=self.handle_row_action,
        ).tooltip("Clone")
        ui.button(
            icon="delete",
            color="negative",
        ).props("flat round size=sm").on(
            "click",
            js_handler="() => emit(props.row.name, 'delete')",
            handler=self.handle_row_action,
        ).tooltip("Delete").disable()

    async def handle_row_action(self, data: GenericEventArguments) -> None:
        """Callback for action buttons on schedule rows"""
        if TYPE_CHECKING:
            target: str
            action: Literal["rules", "clone", "delete"]
        target, action = data.args
        label = self.table_index[target]
        self.show_spinner()

        match action:
            case "rules":
                new_label_dialog = NewNotificationLabelDialog(dialog_title="View Notification Label")
                new_label_dialog.model["spec"] = {
                    "filters": label["filters"],
                    "secret_plaintext": label["secret"],
                }
                new_label_dialog.model["metadata"] = {"name": target, "kind": label["kind"]}
                _ = await new_label_dialog
                # in this case we do nothing with the result
                # TODO do we want to allow an edit here?

            case "clone":
                # Creates an "identical" notification label but we do not copy
                # the name or "secret"
                new_label_dialog = NewNotificationLabelDialog(dialog_title="New Notification Label")
                new_label_dialog.model["spec"] = {
                    "filters": label["filters"],
                }
                new_label_dialog.model["metadata"] = {"kind": label["kind"]}
                if (cloned_label := await new_label_dialog) is not None:
                    await self.save_new_label(cloned_label)

            case "delete":
                confirm = ConfirmationDialog(
                    icon="delete",
                    message="""\
                        Deleting a notification label removes it from the application.
                        This is irreversable and permanent.
                        Any campaigns using this notification label will be unchanged and
                        will ignore it unless a new label with the same name is added in the future.
                    """,
                    show_remember_checkbox=False,
                )
                go_for_it, _ = await confirm
                confirm.clear()
                if go_for_it:
                    await notifications.delete_notification_label(target)
                    ui.notify(f"Label deleted: {target}", color="warning")
            case _ as unreachable:
                assert_never(unreachable)

        await self.create_notifications_table.refresh()
        self.hide_spinner()

    async def handle_new_notification(self, data: ClickEventArguments) -> None:
        """Display a dialog for creating a new notification label and POST
        the result to the API.
        """
        new_label_dialog = NewNotificationLabelDialog(dialog_title="New Notification Label")
        if (new_label := await new_label_dialog) is not None:
            await self.save_new_label(new_label)

    async def save_new_label(self, label: dict) -> None:
        """Save a new label with an API POST"""
        self.show_spinner()
        manifest = NotificationLabelManifest.model_validate(label)
        await notifications.new_notification_label(manifest)
        await self.create_notifications_table.refresh()
        self.hide_spinner()
