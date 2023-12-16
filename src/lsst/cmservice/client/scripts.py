"""python for client API for managing Script tables"""
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import db, models
from ..common.enums import StatusEnum
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for Script
response_model_class = models.Script
# Specify the pydantic model from making new Scripts
create_model_class = models.ScriptCreate
# Specify the pydantic model from updating rows
update_model_class = models.ScriptUpdate
# Specify the associated database table
db_class = db.Script

# Construct derived templates
router_string = f"{db_class.class_string}"


class CMScriptClient:
    """Interface for accessing remote cm-service to manipulate Script Tables"""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    # Add functions to the client class
    get_rows = wrappers.get_rows_no_parent_function(response_model_class, f"{router_string}/list")

    get_row = wrappers.get_row_function(response_model_class, f"{router_string}/get")

    # get_row_by_fullname =

    create = wrappers.create_row_function(
        response_model_class,
        create_model_class,
        f"{router_string}/create",
    )

    update = wrappers.update_row_function(
        response_model_class,
        update_model_class,
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

    update_status = wrappers.get_node_post_query_function(
        response_model_class,
        models.UpdateStatusQuery,
        f"{router_string}/update",
        "status",
    )

    update_collections = wrappers.get_node_post_query_function(
        response_model_class,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "collections",
    )

    update_child_config = wrappers.get_node_post_query_function(
        response_model_class,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "child_config",
    )

    update_data_dict = wrappers.get_node_post_query_function(
        response_model_class,
        models.UpdateNodeQuery,
        f"{router_string}/update",
        "data_dict",
    )

    update_spec_aliases = wrappers.get_node_post_query_function(
        response_model_class,
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
        response_model_class,
        f"{router_string}/action",
        "reject",
    )

    reset = wrappers.get_node_post_no_query_function(
        response_model_class,
        f"{router_string}/action",
        "reset",
    )

    process = wrappers.get_node_post_no_query_function(
        response_model_class,
        f"{router_string}/action",
        "process",
    )

    run_check = wrappers.get_node_post_no_query_function(
        tuple[bool, StatusEnum],
        f"{router_string}/action",
        "run_check",
    )

    reset_script = wrappers.get_node_post_no_query_function(
        StatusEnum,
        f"{router_string}/action",
        "reset_script",
    )

    copy = wrappers.get_node_post_no_query_function(
        response_model_class,
        f"{router_string}/action",
        "copy",
    )
