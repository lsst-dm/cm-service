"""Module implementing reusable and/or modular Dialogs."""

from collections.abc import Callable
from enum import Enum, IntFlag, auto
from typing import TYPE_CHECKING, Self

from nicegui import ui
from nicegui.events import GenericEventArguments

from .. import api
from . import strings


class NodeRecoverAction(Enum):
    """An enumeration of the actions that may be taken to recover a Node from
    a failed state.
    """

    cancel = auto()
    restart = auto()
    retry = auto()
    reset = auto()


class NodeAllowedActions(IntFlag):
    """A flag enumeration declaring which recovery actions are allowed to be
    taken for a Node in a failed state. For example, only Group nodes may be
    subject to "restart" actions.
    """

    restart = auto()
    retry = auto()
    reset = auto()

    @classmethod
    def all(cls) -> Self:
        """Creates a flag where all the available members are set."""
        return ~cls(0)


class NodeRecoveryPopup(ui.dialog):
    """A modal dialog presenting Node recovery options for a Node in a failed
    state.
    """

    def __init__(self, allowed_actions: NodeAllowedActions) -> None:
        super().__init__()
        with self, ui.card():
            ui.label(strings.NODE_RECOVERY_DIALOG_LABEL)
            with ui.row():
                if NodeAllowedActions.restart in allowed_actions:
                    ui.chip(
                        "restart",
                        icon="restart_alt",
                        color="positive",
                        on_click=lambda: self.submit(NodeRecoverAction.restart),
                    ).tooltip(strings.NODE_RESTART_TOOLTIP)
                if NodeAllowedActions.retry in allowed_actions:
                    ui.chip(
                        "retry",
                        icon="replay",
                        color="accent",
                        on_click=lambda: self.submit(NodeRecoverAction.retry),
                    ).tooltip(strings.NODE_RETRY_TOOLTIP)
                if NodeAllowedActions.reset in allowed_actions:
                    ui.chip(
                        "reset",
                        icon="settings_backup_restore",
                        color="negative",
                        on_click=lambda: self.submit(NodeRecoverAction.reset),
                    ).tooltip(strings.NODE_RESET_TOOLTIP)
                ui.chip(
                    "cancel",
                    icon="cancel",
                    color="negative",
                    on_click=lambda: self.submit(NodeRecoverAction.cancel),
                ).tooltip("Never mind.")

    @classmethod
    async def click(cls, e: GenericEventArguments, node: dict, refreshable: Callable) -> None:
        """Callback method for a click event from an element on a Node Recovery
        Popup dialog.
        """
        if TYPE_CHECKING:
            assert hasattr(refreshable, "refresh")

        allowed_actions = NodeAllowedActions.all()
        if node["kind"] != "group":
            allowed_actions &= ~NodeAllowedActions.restart
        result = await cls(allowed_actions)

        match result:
            case NodeRecoverAction.restart:
                await api.retry_restart_node(n0=node["id"], force=True)
            case NodeRecoverAction.retry:
                await api.retry_restart_node(n0=node["id"], force=False)
            case NodeRecoverAction.reset:
                ui.notify("Resetting node")
            case _:
                # including the cancel case
                ...

        refreshable.refresh()
