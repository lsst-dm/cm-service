"""python for client API for managing Group tables"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import db, models
from ..common.enums import StatusEnum
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient

# Template specialization
# Specify the pydantic model for Group
ResponseModelClass = models.Group
# Specify the pydantic model from making new Groups
CreateModelClass = models.GroupCreate
# Specify the pydantic model from updating rows
UpdateModelClass = models.GroupUpdate
# Specify the associated database table
DbClass = db.Group

# Construct derived templates
router_string = f"{DbClass.class_string}"


class CMGroupClient:
    """Interface for accessing remote cm-service to manipulate
    Group Tables
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
        ResponseModelClass, f"{router_string}/get_row_by_name"
    )

    get_row_by_fullname = wrappers.get_row_by_fullname_function(
        ResponseModelClass, f"{router_string}/get_row_by_fullname"
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

    reset = wrappers.get_node_post_no_query_function(
        ResponseModelClass,
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

    get_scripts = wrappers.get_general_query_function(
        models.ScriptQuery,
        list[models.Script],
        f"{router_string}/get",
        "scripts",
    )

    get_all_scripts = wrappers.get_general_query_function(
        models.ScriptQuery,
        list[models.Script],
        f"{router_string}/get",
        "all_scripts",
    )

    get_jobs = wrappers.get_general_query_function(
        models.JobQuery,
        list[models.Job],
        f"{router_string}/get",
        "jobs",
    )

    retry_script = wrappers.get_general_post_function(
        models.ScriptQuery,
        models.Script,
        f"{router_string}/action",
        "retry_script",
    )

    estimate_sleep_time = wrappers.get_node_post_query_function(
        int,
        models.SleepTimeQuery,
        f"{router_string}/get",
        "sleep_time",
    )

    rescue_job = wrappers.get_node_post_query_function(
        models.Job,
        models.NodeQuery,
        f"{router_string}/action",
        "rescue_job",
    )

    mark_rescued = wrappers.get_node_post_query_function(
        list[models.Job],
        models.NodeQuery,
        f"{router_string}/action",
        "mark_rescued",
    )

    get_wms_task_reports = wrappers.get_node_property_function(
        models.MergedWmsTaskReportDict,
        f"{router_string}/get",
        "wms_task_reports",
    )

    get_tasks = wrappers.get_node_property_function(
        models.MergedTaskSetDict,
        f"{router_string}/get",
        "tasks",
    )

    get_products = wrappers.get_node_property_function(
        models.MergedProductSetDict,
        f"{router_string}/get",
        "products",
    )
