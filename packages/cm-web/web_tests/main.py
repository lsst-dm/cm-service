"""NiceGUI main file for the simulated `user` fixture.

The user simulation resets NiceGUI's global state, including its page routes,
for every test and then executes this file. The cm-web page routes are
registered as an import side effect of the `pages` module, so the module is
reloaded here to register them again for each test.
"""

import importlib
import sys

from nicegui import ui

if (pages := sys.modules.get("lsst.cmservice.web.pages")) is not None:
    importlib.reload(pages)
else:
    importlib.import_module("lsst.cmservice.web.pages")

ui.run(storage_secret="simulated secret")
