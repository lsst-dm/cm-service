from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient


class CMQueryClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    get_productions = wrappers.get_rows_no_parent_function(models.Production, "production/list")

    get_campaigns = wrappers.get_rows_function(models.Campaign, "campaign/list")

    get_steps = wrappers.get_rows_function(models.Step, "step/list")

    get_groups = wrappers.get_rows_function(models.Group, "group/list")

    get_jobs = wrappers.get_rows_function(models.Job, "job/list")

    get_scripts = wrappers.get_rows_function(models.Script, "script/list")

    get_specifications = wrappers.get_rows_no_parent_function(models.Specification, "specification/list")

    get_spec_blocks = wrappers.get_rows_no_parent_function(models.SpecBlock, "spec_block/list")

    get_script_templates = wrappers.get_rows_no_parent_function(models.ScriptTemplate, "script_template/list")

    get_pipetask_error_types = wrappers.get_rows_no_parent_function(
        models.PipetaskErrorType,
        "pipetask_error_type/list",
    )

    get_pipetask_errors = wrappers.get_rows_no_parent_function(models.PipetaskError, "pipetask_error/list")

    get_script_errors = wrappers.get_rows_no_parent_function(models.ScriptError, "script_error/list")

    get_task_sets = wrappers.get_rows_no_parent_function(models.TaskSet, "task_set/list")

    get_product_sets = wrappers.get_rows_no_parent_function(models.ProductSet, "product_set/list")

    get_wms_task_reports = wrappers.get_rows_no_parent_function(models.WmsTaskReport, "wms_task_report/list")

    get_element = wrappers.get_object_by_fullname_function(models.Element, "get/element")

    get_script = wrappers.get_object_by_fullname_function(models.Script, "get/script")

    get_job = wrappers.get_object_by_fullname_function(models.Job, "get/job")

    get_spec_block = wrappers.get_object_by_fullname_function(models.SpecBlock, "get/spec_block")

    get_specification = wrappers.get_object_by_fullname_function(models.Specification, "get/specification")

    get_resolved_collections = wrappers.get_node_property_function(dict, "get/resolved_collections")

    get_collections = wrappers.get_node_property_function(dict, "get/collections")

    get_child_config = wrappers.get_node_property_function(dict, "get/child_config")

    get_spec_aliases = wrappers.get_node_property_function(dict, "get/spec_aliases")

    get_data_dict = wrappers.get_node_property_function(dict, "get/data_dict")

    get_prerequisites = wrappers.get_node_property_function(dict, "get/prerequisites")

    get_job_task_sets = wrappers.get_job_property_function(models.TaskSet, "get/job/task_sets")

    get_job_wms_reports = wrappers.get_job_property_function(models.WmsTaskReport, "get/job/wms_reports")

    get_job_product_sets = wrappers.get_job_property_function(models.ProductSet, "get/job/product_sets")

    get_job_errors = wrappers.get_job_property_function(models.PipetaskError, "get/job/errors")
