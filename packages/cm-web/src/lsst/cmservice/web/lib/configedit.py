from collections.abc import Awaitable, Callable
from functools import partial

from nicegui import ui

from .. import api
from .configdiff import patch_resource

type Callback = Callable[[dict], Awaitable[None]]


async def validate_name(name: str) -> bool:
    """validation callback for input fields allowing naming components.
    Generally forces these names to be lower-case snake_case.
    """
    ...


async def handle_name_change(name: str) -> None:
    """on change callback for input fields allowing naming components.
    Forces the name to be lower-case snake_case.
    """
    ...


async def get_data(editor: ui.json_editor, dialog: ui.dialog) -> None:
    """Fetches data from an editor and"""
    data = await editor.run_editor_method("get")
    dialog.submit(data)


async def configuration_edit(
    manifest_id: str,
    namespace: str,
    kind: str = "node",
    *,
    readonly: bool = False,
    callback: Callback | None = None,
) -> None:
    """Produces a JSON Editor dialog for a given manifest, allowing content
    to be revied or changes made.

    On submit, changes are used to issue a PATCH to the manifest API.

    Parameters
    ----------
    callback : Callable[[dict], Awaitable[None]]
        An awaitable callback function to invoke at the end of the edit process
        as effectively a tail-call. The function takes a single parameter --
        the value returned from the dialog, so a more complex callback should
        be prepared as a `partial`.
    """
    dialog_title = f"Editing {kind.title()} Configuration"
    # get current configuration of manifest/node from db
    if kind == "node":
        manifest_response = await api.get_one_node(id=manifest_id, namespace=namespace)
    else:
        manifest_response = await api.get_one_manifest(id=manifest_id, namespace=namespace)
    if manifest_response is None:
        return None
    manifest_url = manifest_response.headers["Self"]
    manifest = manifest_response.json()
    manifest_name = manifest["name"]

    current_configuration = manifest.get("spec") or manifest.get("configuration", {})
    with ui.dialog().props("full-height full-width") as dialog, ui.card().classes("w-full"):
        ui.label(dialog_title).classes("text-h5")
        name_edit = ui.input(placeholder=manifest_name)
        editor = ui.json_editor(
            {"content": {"json": current_configuration}, "mode": "text"},
        ).classes("w-full h-full")
        with ui.card_actions():
            if not readonly:
                get_data_partial = partial(get_data, dialog=dialog, editor=editor)
                ui.button("Done", color="positive", on_click=get_data_partial).props("style: flat")
            ui.button("Cancel", color="negative", on_click=lambda: dialog.submit(None)).props("style: flat")

    result = await dialog
    if result is not None:
        # TODO run.io_bound
        if manifest["version"] == 0:
            # Library manifests are first copied to the campaign namespace, so
            # what was Library version 0 is now also Campaign version 1.
            # FIXME: this is confusing, and necessary only insofar as we are
            # getting a "manifest_url" appropriate for the patch operation.
            r = await api.put_one_manifest(manifest_id, name_edit.value, namespace)
            manifest_url = r.headers["Self"]

        await patch_resource(manifest_url, current_configuration, result)

        if callback is not None:
            await callback(result)
