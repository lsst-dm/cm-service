from nicegui import app, ui

from .. import pages as pages
from ..lib.logging import LOGGER
from ..settings import settings

logger = LOGGER.bind(module=__name__)

app.add_static_files("/static", settings.static_dir)

ui.run(
    title="Campaign Management",
    port=settings.server_port,
    favicon=settings.static_dir / "favicon.png",
    storage_secret=settings.storage_secret,
)
