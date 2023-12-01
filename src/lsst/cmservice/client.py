from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

import httpx
from pydantic import BaseModel, ValidationError, parse_obj_as

from . import models
from .common.enums import StatusEnum

__all__ = ["CMClient"]


def get_object_by_fullname_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def get_obj_by_fullname(
        obj: CMClient,
        fullname: str,
    ) -> response_model_class:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        results = obj._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(response_model_class, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return get_obj_by_fullname


def get_node_property_function(
    response_model_class: TypeAlias,
    query: str = "",
) -> Callable:
    def get_node_property(
        obj: CMClient,
        fullname: str,
    ) -> response_model_class:
        params = models.NodeQuery(
            fullname=fullname,
        )
        results = obj._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(response_model_class, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return get_node_property


def get_job_property_function(
    response_model_class: TypeAlias,
    query: str = "",
) -> Callable:
    def get_job_property(
        obj: CMClient,
        fullname: str,
    ) -> list[response_model_class]:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        results = obj._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[response_model_class], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return get_job_property


def get_general_post_function(
    query_class: TypeAlias = BaseModel,
    response_model_class: TypeAlias = Any,
    query: str = "",
    results_key: str | None = None,
) -> Callable:
    def general_post_function(
        obj: CMClient,
        **kwargs: Any,
    ) -> response_model_class:
        params = query_class(**kwargs)
        results = obj._client.post(f"{query}", content=params.json()).json()
        try:
            if results_key is None:
                return parse_obj_as(response_model_class, results["status"])
            else:
                return parse_obj_as(response_model_class, results[results_key])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return general_post_function


def get_rows_no_parent_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def get_rows(obj: CMClient) -> list[response_model_class]:
        the_list: list[response_model_class] = []
        params = {"skip": 0}
        while (results := obj._client.get(f"{query}", params=params).json()) != []:
            the_list.extend(parse_obj_as(list[response_model_class], results))
            params["skip"] += len(results)
        return the_list

    return get_rows


def get_rows_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def get_rows(
        obj: CMClient,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[response_model_class]:
        the_list: list[response_model_class] = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        while (results := obj._client.get(f"{query}", params=params).json()) != []:
            the_list.extend(parse_obj_as(list[response_model_class], results))
            params["skip"] += len(results)
        return the_list

    return get_rows


def create_row_function(
    response_model_class: TypeAlias = BaseModel,
    create_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def row_create(obj: CMClient, **kwargs: Any) -> response_model_class:
        params = create_model_class(**kwargs)
        results = obj._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(response_model_class, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return row_create


def update_row_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def row_update(
        obj: CMClient,
        row_id: int,
        **kwargs: Any,
    ) -> response_model_class:
        params = response_model_class(id=row_id, **kwargs)
        full_query = f"{query}/{row_id}"
        results = obj._client.put(f"{full_query}", content=params.json()).json()
        try:
            return parse_obj_as(response_model_class, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return row_update


def delete_row_function(
    query: str = "",
) -> Callable:
    def row_delete(
        obj: CMClient,
        row_id: int,
    ) -> None:
        full_query = f"{query}/{row_id}"
        obj._client.delete(f"{full_query}")

    return row_delete


class CMClient:
    """Interface for accessing remote cm-service."""

    def __init__(self: CMClient, url: str) -> None:
        self._client = httpx.Client(base_url=url)

    get_element = get_object_by_fullname_function(models.Element, "get/element")

    get_script = get_object_by_fullname_function(models.Script, "get/script")

    get_job = get_object_by_fullname_function(models.Job, "get/job")

    get_spec_block = get_object_by_fullname_function(models.SpecBlock, "get/spec_block")

    get_specification = get_object_by_fullname_function(models.Specification, "get/specification")

    get_resolved_collections = get_node_property_function(dict, "get/resolved_collections")

    get_collections = get_node_property_function(dict, "get/collections")

    get_child_config = get_node_property_function(dict, "get/child_config")

    get_spec_aliases = get_node_property_function(dict, "get/spec_aliases")

    get_data_dict = get_node_property_function(dict, "get/data_dict")

    get_prerequisites = get_node_property_function(dict, "get/prerequisites")

    get_job_task_sets = get_job_property_function(models.TaskSet, "get/job/task_sets")

    get_job_wms_reports = get_job_property_function(models.WmsTaskReport, "get/job/wms_reports")

    get_job_product_sets = get_job_property_function(models.ProductSet, "get/job/product_sets")

    get_job_errors = get_job_property_function(models.PipetaskError, "get/job/errors")

    update_status = get_general_post_function(models.UpdateStatusQuery, StatusEnum, "update/status", "status")

    update_collections = get_general_post_function(
        models.UpdateNodeQuery,
        dict,
        "update/collections",
        "collections",
    )

    update_data_dict = get_general_post_function(models.UpdateNodeQuery, dict, "update/data_dict", "data")

    update_spec_aliases = get_general_post_function(
        models.UpdateNodeQuery,
        dict,
        "update/spec_aliases",
        "spec_aliases",
    )

    update_child_config = get_general_post_function(
        models.UpdateNodeQuery,
        dict,
        "update/child_config",
        "child_config",
    )

    add_groups = get_general_post_function(models.AddGroups, list[models.Group], "add/groups")

    add_steps = get_general_post_function(models.AddSteps, list[models.Step], "add/steps")

    add_campaign = get_general_post_function(models.CampaignCreate, models.Campaign, "add/campaign")

    load_specification = get_general_post_function(
        models.SpecificationLoad,
        models.Specification,
        "load/specification",
    )

    load_campaign = get_general_post_function(models.LoadAndCreateCampaign, models.Campaign, "load/campaign")

    load_error_types = get_general_post_function(
        models.YamlFileQuery,
        list[models.PipetaskErrorType],
        "load/error_types",
    )

    load_manifest_report = get_general_post_function(
        models.LoadManifestReport,
        models.Job,
        "load/manifest_report",
    )

    process = get_general_post_function(models.NodeQuery, StatusEnum, "actions/process")

    retry_script = get_general_post_function(models.ScriptQueryBase, models.Script, "actions/retry_script")

    rescue_script = get_general_post_function(models.ScriptQueryBase, models.Script, "actions/rescue_script")

    mark_script_rescued = get_general_post_function(
        models.ScriptQueryBase,
        list[models.Script],
        "actions/mark_script_rescued",
    )

    rematch_errors = get_general_post_function(
        models.RematchQuery,
        list[models.PipetaskError],
        "actions/rematch_errors",
    )

    get_productions = get_rows_no_parent_function(models.Production, "productions")

    get_campaigns = get_rows_function(models.Campaign, "campaigns")

    get_steps = get_rows_function(models.Step, "steps")

    get_groups = get_rows_function(models.Group, "group")

    get_jobs = get_rows_function(models.Job, "job")

    get_scripts = get_rows_function(models.Job, "job")

    get_specifications = get_rows_no_parent_function(models.Specification, "specifications")

    get_spec_blocks = get_rows_no_parent_function(models.SpecBlock, "spec_blocks")

    get_script_templates = get_rows_no_parent_function(models.ScriptTemplate, "script_templates")

    get_pipetask_error_types = get_rows_no_parent_function(models.PipetaskErrorType, "pipetask_error_types")

    get_pipetask_errors = get_rows_no_parent_function(models.PipetaskError, "pipetask_errors")

    get_script_errors = get_rows_no_parent_function(models.ScriptError, "script_errors")

    get_task_sets = get_rows_no_parent_function(models.TaskSet, "task_sets")

    get_product_sets = get_rows_no_parent_function(models.ProductSet, "product_sets")

    get_wms_task_reports = get_rows_no_parent_function(models.WmsTaskReport, "wms_task_reports")

    get_script_dependencies = get_rows_no_parent_function(models.Dependency, "script_dependencies")

    get_step_dependencies = get_rows_no_parent_function(models.Dependency, "step_dependencies")

    production_create = create_row_function(models.Production, models.ProductionCreate, "productions")

    production_update = update_row_function(models.Production, "productions")

    production_delete = delete_row_function("productions")

    campaign_create = create_row_function(models.Campaign, models.CampaignCreate, "campaigns")

    campaign_update = update_row_function(models.Campaign, "campaigns")

    campaign_delete = delete_row_function("campaigns")

    def get_element_scripts(
        self,
        fullname: str,
        script_name: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Script]:
        params = models.ScriptQuery(
            fullname=fullname,
            script_name=script_name,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/scripts"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.Script], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_element_jobs(
        self,
        fullname: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Job]:
        params = models.JobQuery(
            fullname=fullname,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/element_jobs"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.Job], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg
