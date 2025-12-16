from typing import Any

from nicegui import ui

from .common import cm_frame


def handle_export(e: Any) -> None:
    """Handles the export of graph data from the Svelte-Flow canvas."""
    graph_data = e.args
    ui.notify(f"""Exported {len(graph_data["nodes"])} nodes""")


@ui.page("/canvas")
def canvas() -> None:
    ui.add_head_html("""<script src="/static/cm-canvas-bundle.iife.js"></script>""")

    with cm_frame("Campaign Canvas"):
        with ui.column().classes("w-full h-full"):
            ui.element("div").classes("w-full h-full").props('id="flow-container"')
            ui.run_javascript("""
                window.flowInstance = initializeFlow('flow-container', {
                    onExport: (data) => emitEvent("export", data)
                });
            """)
            ui.on("export", handle_export)
