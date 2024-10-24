from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from pydantic import TypeAdapter, ValidationError

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
        """Return the httpx.Client"""
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

    get_step_dependencies = wrappers.get_rows_function(models.Dependency, "step_dependency/list")

    get_script_dependencies = wrappers.get_rows_function(models.Dependency, "script_dependency/list")

    get_pipetask_error_types = wrappers.get_rows_no_parent_function(
        models.PipetaskErrorType,
        "pipetask_error_type/list",
    )

    get_pipetask_errors = wrappers.get_rows_no_parent_function(models.PipetaskError, "pipetask_error/list")

    get_script_errors = wrappers.get_rows_no_parent_function(models.ScriptError, "script_error/list")

    get_task_sets = wrappers.get_rows_no_parent_function(models.TaskSet, "task_set/list")

    get_product_sets = wrappers.get_rows_no_parent_function(models.ProductSet, "product_set/list")

    get_wms_task_reports = wrappers.get_rows_no_parent_function(models.WmsTaskReport, "wms_task_report/list")

    get_queues = wrappers.get_rows_no_parent_function(models.Queue, "queue/list")

    get_script = wrappers.get_row_by_fullname_function(models.Script, "get/script")

    get_job = wrappers.get_row_by_fullname_function(models.Job, "get/job")

    get_spec_block = wrappers.get_node_property_by_fullname_function(models.SpecBlock, "get/spec_block")

    get_specification = wrappers.get_node_property_by_fullname_function(
        models.Specification, "get/specification"
    )

    get_resolved_collections = wrappers.get_node_property_by_fullname_function(
        dict,
        "get/resolved_collections",
    )

    get_collections = wrappers.get_node_property_by_fullname_function(dict, "get/collections")

    get_child_config = wrappers.get_node_property_by_fullname_function(dict, "get/child_config")

    get_spec_aliases = wrappers.get_node_property_by_fullname_function(dict, "get/spec_aliases")

    get_data_dict = wrappers.get_node_property_by_fullname_function(dict, "get/data_dict")

    get_prerequisites = wrappers.get_node_property_function(dict, "get/prerequisites")

    get_job_task_sets = wrappers.get_job_property_function(models.TaskSet, "get/job/task_sets")

    get_job_wms_reports = wrappers.get_job_property_function(models.WmsTaskReport, "get/job/wms_reports")

    get_job_product_sets = wrappers.get_job_property_function(models.ProductSet, "get/job/product_sets")

    get_job_errors = wrappers.get_job_property_function(models.PipetaskError, "get/job/errors")

    def get_element_scripts(
        self,
        fullname: str,
        script_name: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Script]:
        """Return the `Script`s associated to an element

        Parameters
        ----------
        fullname: str
            Fullname of the Element in question

        script_name: str | None
            If provided, only return scripts with this name

        remaining_only: bool
            If True only include Scripts that are not revieable or accepted

        skip_superseded: bool
            If True don't inlcude Scripts that are marked superseded

        Returns
        -------
        scripts : List[Script]
            The requested scripts
        """
        params = models.ScriptQuery(
            fullname=fullname,
            script_name=script_name,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/element_scripts"
        results = self._client.get(f"{query}", params=params.model_dump()).json()
        try:
            return TypeAdapter(list[models.Script]).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_element_all_scripts(
        self,
        fullname: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Script]:
        """Return all the scripts associated to an ELement

        Parameters
        ----------
        fullname: str
            Fullname of the Element in question

        remaining_only: bool
            If True only include Scripts that are not revieable or accepted

        skip_superseded: bool
            If True don't inlcude Scripts that are marked superseded

        Returns
        -------
        scripts : List[Script]
            The requested scripts
        """
        params = models.ScriptQuery(
            fullname=fullname,
            script_name=None,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/element_all_scripts"
        results = self._client.get(f"{query}", params=params.model_dump()).json()
        try:
            return TypeAdapter(list[models.Script]).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_element_jobs(
        self,
        fullname: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Job]:
        """Return all the jobs associated to an ELement

        Parameters
        ----------
        fullname: str
            Fullname of the Element in question

        remaining_only: bool
            If True only include Scripts that are not revieable or accepted

        skip_superseded: bool
            If True don't inlcude Scripts that are marked superseded

        Returns
        -------
        jobs : List[Job]
            The requested jobs
        """
        params = models.JobQuery(
            fullname=fullname,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/element_jobs"
        results = self._client.get(f"{query}", params=params.model_dump()).json()
        try:
            return TypeAdapter(list[models.Job]).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_element_sleep(
        self,
        fullname: str,
    ) -> int:
        """Estimate how long to sleep before calling process again

        Parameters
        ----------
        fullname : str
            Fullname of element in question

        Returns
        -------
        sleep_time : int
            Time to sleep in seconds
        """
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/element_sleep_ime"
        results = self._client.get(f"{query}", params=params.model_dump()).json()
        try:
            return TypeAdapter(int).validate_json(results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg
