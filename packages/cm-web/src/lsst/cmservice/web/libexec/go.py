from pathlib import Path

from nicegui import app, ui

from .. import pages as pages
from ..lib.logging import LOGGER
from ..settings import settings

logger = LOGGER.bind(module=__name__)

static_path = Path(__file__).parent.parent / "static"

app.add_static_files("/static", static_path)

ui.run(
    title="Campaign Management",
    port=settings.server_port,
    favicon=static_path / "favicon.png",
    storage_secret="justbetweenyouandme",
)
