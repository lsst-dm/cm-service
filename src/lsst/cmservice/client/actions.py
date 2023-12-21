from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import models
from ..common.enums import StatusEnum
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient


class CMActionClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client

    process = wrappers.get_general_post_function(
        models.ProcessQuery,
        tuple[bool, StatusEnum],
        "actions/process",
    )

    reset_script = wrappers.get_general_post_function(
        models.UpdateStatusQuery,
        models.Script,
        "actions/reset_script",
    )

    retry_script = wrappers.get_general_post_function(
        models.ScriptQueryBase,
        models.Script,
        "actions/retry_script",
    )

    rescue_script = wrappers.get_general_post_function(
        models.ScriptQueryBase,
        models.Script,
        "actions/rescue_script",
    )

    mark_script_rescued = wrappers.get_general_post_function(
        models.ScriptQueryBase,
        list[models.Script],
        "actions/mark_script_rescued",
    )

    rematch_errors = wrappers.get_general_post_function(
        models.RematchQuery,
        list[models.PipetaskError],
        "actions/rematch_errors",
    )
