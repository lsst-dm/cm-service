from nicegui import app, ui

from .. import pages as pages
from ..lib.logging import LOGGER
from ..settings import settings

logger = LOGGER.bind(module=__name__)

app.add_static_files(settings.static_endpoint, settings.static_dir)

ui.run(
    title="Campaign Management",
    port=settings.server_port,
    favicon=settings.static_dir / "favicon.png",
    storage_secret=settings.storage_secret,
    reconnect_timeout=settings.reconnect_timeout,
    reload=(not settings.production),
    show=(not settings.production),
    # NOTE the following kwargs are passed to uvicorn.run
    root_path=settings.root_path,
    ws_max_size=16777216,
    ws_max_queue=32,
    ws_ping_interval=20.0,
    ws_ping_timeout=20.0,
    ws_per_message_deflate=True,
)
