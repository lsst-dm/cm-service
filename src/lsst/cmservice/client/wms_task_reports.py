"""python for client API for managing WmsTaskReport tables"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import db, models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for WmsTaskReport
ResponseModelClass = models.WmsTaskReport
# Specify the pydantic model from making new WmsTaskReport
CreateModelClass = models.WmsTaskReportCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.WmsTaskReportUpdate
# Specify the associated database table
DbClass = db.WmsTaskReport

# Construct derived templates
router_string = f"{DbClass.class_string}"


class CMWmsTaskReportClient:
    """Interface for accessing remote cm-service to manipulate
    WmsTaskReport Tables
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

    # get_row_by_fullname =

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
