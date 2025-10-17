from functools import partial

from nicegui import ui

from .. import api
from .configdiff import patch_resource


async def get_data(editor: ui.json_editor, dialog: ui.dialog) -> None:
    """Fetches data from an editor and"""
    data = await editor.run_editor_method("get")
    dialog.submit(data)


async def configuration_edit(manifest_id: str, namespace: str, *, readonly: bool = False) -> None:
    """Produces a JSON Editor dialog for a given manifest, allowing content
    to be revied or changes made.

    On submit, changes are used to issue a PATCH to the manifest API.
    """
    # get current configuration of manifest/node from db
    manifest_response = await api.get_one_manifest(id=manifest_id, namespace=namespace)
    if manifest_response is None:
        return None
    manifest_url = manifest_response.headers["Self"]
    manifest = manifest_response.json()
    manifest_name = manifest["name"]

    current_configuration = manifest.get("spec") or manifest.get("configuration", {})
    with ui.dialog().props("full-height") as dialog, ui.card().style("width: 75vw"):
        ui.label("Editing Configuration")
        name_edit = ui.input(placeholder=manifest_name)
        editor = ui.json_editor(
            {"content": {"json": current_configuration}},
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
