"""python for client API for managing ScriptTemplate tables"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import db, models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for ScriptTemplate
ResponseModelClass = models.ScriptTemplate
# Specify the pydantic model from making new ScriptTemplates
CreateModelClass = models.ScriptTemplateCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.ScriptTemplateUpdate
# Specify the associated database table
DbClass = db.ScriptTemplate

# Construct derived templates
router_string = f"{DbClass.class_string}"


class CMScriptTemplateClient:
    """Interface for accessing remote cm-service to manipulate
    ScriptTemplate Tables
    """

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client

    # Add functions to the client class
    get_rows = wrappers.get_rows_no_parent_function(ResponseModelClass, f"{router_string}/list")

    get_row = wrappers.get_row_function(ResponseModelClass, f"{router_string}/get")

    get_row_by_name = wrappers.get_row_by_name_function(
        ResponseModelClass,
        f"{router_string}/get_row_by_name",
    )

    create = wrappers.create_row_function(
        ResponseModelClass,
        CreateModelClass,
        f"{router_string}/create",
    )

    update = wrappers.update_row_function(
        ResponseModelClass,
        UpdateModelClass,
        f"{router_string}/update",
    )

    delete = wrappers.delete_row_function(f"{router_string}/delete")
