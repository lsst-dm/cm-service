"""python for client API for managing Script tables"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import StatusEnum, db, models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for Script
ResponseModelClass = models.Script
# Specify the pydantic model from making new Scripts
CreateModelClass = models.ScriptCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.ScriptUpdate
# Specify the associated database table
DbClass = db.Script

# Construct derived templates
router_string = f"{DbClass.class_string}"


class CMScriptClient:
    """Interface for accessing remote cm-service to manipulate Script Tables"""

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

    get_spec_block = wrappers.get_node_property_function(
        models.SpecBlock,
        f"{router_string}/get",
        "spec_block",
    )

    get_specification = wrappers.get_node_property_function(
        models.Specification,
        f"{router_string}/get",
        "specification",
    )

    get_parent = wrappers.get_node_property_function(
        models.Element,
        f"{router_string}/get",
        "parent",
    )

    get_resolved_collections = wrappers.get_node_property_function(
        dict,
        f"{router_string}/get",
        "resolved_collections",
    )

    get_collections = wrappers.get_node_property_function(dict, f"{router_string}/get", "collections")

    get_child_config = wrappers.get_node_property_function(dict, f"{router_string}/get", "child_config")

    get_data_dict = wrappers.get_node_property_function(dict, f"{router_string}/get", "data_dict")

    get_spec_aliases = wrappers.get_node_property_function(dict, f"{router_string}/get", "spec_aliases")

    get_script_errors = wrappers.get_node_property_function(
        list[models.ScriptError],
        f"{router_string}/get",
        "script_errors",
    )

    update_status = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.UpdateStatusQuery,
        f"{router_string}/update",
        "status",
    )

    update_collections = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "collections",
    )

    update_child_config = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "child_config",
    )

    update_data_dict = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "data_dict",
    )

    update_spec_aliases = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "spec_aliases",
    )

    accept = wrappers.get_node_post_no_query_function(
        tuple[bool, StatusEnum],
        f"{router_string}/action",
        "accept",
    )

    reject = wrappers.get_node_post_no_query_function(
        ResponseModelClass,
        f"{router_string}/action",
        "reject",
    )

    reset = wrappers.get_node_post_query_function(
        ResponseModelClass,
        models.ResetQuery,
        f"{router_string}/action",
        "reset",
    )

    process = wrappers.get_node_post_no_query_function(
        ResponseModelClass,
        f"{router_string}/action",
        "process",
    )

    run_check = wrappers.get_node_post_no_query_function(
        tuple[bool, StatusEnum],
        f"{router_string}/action",
        "run_check",
    )

    reset_script = wrappers.get_node_post_query_function(
        StatusEnum,
        models.ResetQuery,
        f"{router_string}/action",
        "reset_script",
    )
