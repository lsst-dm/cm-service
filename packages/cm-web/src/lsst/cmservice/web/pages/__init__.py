"""Module for Nicegui pages.

Each module that adds page routes to the nicegui application should be imported
here to ensure that the complete application takes form on startup.

Note: Any module that adds pages or routes should not have a `from __future__
import annotations` line, as this may interfere with certain runtime type
resolution mechanisms in NiceGUI and/or FastAPI.
"""
from .campaign_detail import campaign_detail as campaign_detail
from .node_detail import node_detail as node_detail
