from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TypeAlias

import httpx
import pause
from pydantic import BaseModel, ValidationError, parse_obj_as

from .. import models
from ..common.enums import StatusEnum
from .campaigns import CMCampaignClient
from .groups import CMGroupClient
from .jobs import CMJobClient
from .queries import CMQueryClient
from .steps import CMStepClient

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
        results = obj.client.get(f"{query}", params=params.dict()).json()
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
        results = obj.client.get(f"{query}", params=params.dict()).json()
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
        results = obj.client.get(f"{query}", params=params.dict()).json()
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
        results = obj.client.post(f"{query}", content=params.json()).json()
        try:
            if results_key is None:
                return parse_obj_as(response_model_class, results)
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
        while (results := obj.client.get(f"{query}", params=params).json()) != []:
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
        while (results := obj.client.get(f"{query}", params=params).json()) != []:
            the_list.extend(parse_obj_as(list[response_model_class], results))
            params["skip"] += len(results)
        return the_list

    return get_rows


def get_row_function(
    response_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def row_get(
        obj: CMClient,
        row_id: int,
    ) -> response_model_class:
        full_query = f"{query}/{row_id}"
        results = obj.client.get(f"{full_query}").json()
        try:
            return parse_obj_as(response_model_class, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    return row_get


def create_row_function(
    response_model_class: TypeAlias = BaseModel,
    create_model_class: TypeAlias = BaseModel,
    query: str = "",
) -> Callable:
    def row_create(obj: CMClient, **kwargs: Any) -> response_model_class:
        params = create_model_class(**kwargs)
        results = obj.client.post(f"{query}", content=params.json()).json()
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
        results = obj.client.put(f"{full_query}", content=params.json()).json()
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
        obj.client.delete(f"{full_query}")

    return row_delete


class CMClient:
    """Interface for accessing remote cm-service."""

    def __init__(self: CMClient, url: str) -> None:
        self._client = httpx.Client(base_url=url)
        self.campaign = CMCampaignClient(self)
        self.step = CMStepClient(self)
        self.group = CMGroupClient(self)
        self.job = CMJobClient(self)
        self.query = CMQueryClient(self)

    @property
    def client(self) -> httpx.Client:
        return self._client

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

    process = get_general_post_function(models.ProcessQuery, tuple[bool, StatusEnum], "actions/process")

    reset_script = get_general_post_function(models.UpdateStatusQuery, models.Script, "actions/reset_script")

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

    queue_create = create_row_function(models.Queue, models.QueueCreate, "queues")

    queue_update = update_row_function(models.Queue, "queues")

    queue_delete = delete_row_function("queues")

    queue_get = get_row_function(models.Queue, "queues")

    def queue_sleep_time(
        self,
        row_id: int,
    ) -> int:
        results = self._client.get(f"queues/sleep_time/{row_id}").json()
        try:
            return parse_obj_as(int, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def queue_process(
        self,
        row_id: int,
    ) -> bool:
        results = self._client.get(f"queues/process/{row_id}").json()
        try:
            return parse_obj_as(bool, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def queue_pause_until_next_check(
        self,
        row_id: int,
    ) -> None:
        queue = self.queue_get(row_id)
        sleep_time = self.queue_sleep_time(row_id)
        wait_time = min(sleep_time, queue.interval)
        delta_t = timedelta(seconds=wait_time)
        next_check = queue.time_updated + delta_t
        now = datetime.now()
        print(now, sleep_time, wait_time, next_check)
        if now < next_check:
            print("pausing")
            pause.until(next_check)

    def queue_daemon(
        self,
        row_id: int,
    ) -> None:
        can_continue = True
        while can_continue:
            self.queue_pause_until_next_check(row_id)
            try:
                can_continue = self.queue_process(row_id)
            except Exception:  # pylint: disable=broad-exception-caught
                can_continue = True

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
        query = "get/element_scripts"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.Script], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_element_all_scripts(
        self,
        fullname: str,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[models.Script]:
        params = models.ScriptQuery(
            fullname=fullname,
            script_name=None,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        query = "get/element_all_scripts"
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

    def get_element_sleep(
        self,
        fullname: str,
    ) -> int:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/element_sleep_time"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(int, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg
