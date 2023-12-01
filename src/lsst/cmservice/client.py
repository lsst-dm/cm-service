from typing import Any

import httpx
from pydantic import ValidationError, parse_obj_as

from . import models
from .common.enums import StatusEnum

__all__ = ["CMClient"]


class CMClient:
    """Interface for accessing remote cm-service."""

    def __init__(self: "CMClient", url: str) -> None:
        self._client = httpx.Client(base_url=url)

    def get_element(self, fullname: str) -> models.Element:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/element"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Element, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_script(self, fullname: str) -> models.Script:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/script"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Script, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_job(self, fullname: str) -> models.Job:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/job"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Job, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_spec_block(
        self,
        fullname: str,
    ) -> models.SpecBlock:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/spec_block"

        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.SpecBlock, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_specification(
        self,
        fullname: str,
    ) -> models.Specification:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/specification"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Specification, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_resolved_collections(
        self,
        fullname: str,
    ) -> dict:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/resolved_collections"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(dict, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_collections(
        self,
        fullname: str,
    ) -> dict:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/collections"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(dict, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_child_config(
        self,
        fullname: str,
    ) -> dict:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/child_config"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(dict, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_spec_aliases(
        self,
        fullname: str,
    ) -> dict:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/spec_aliases"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(dict, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_data_dict(
        self,
        fullname: str,
    ) -> dict:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/data_dict"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(dict, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_prerequisites(
        self,
        fullname: str,
    ) -> bool:
        params = models.NodeQuery(
            fullname=fullname,
        )
        query = "get/prerequisites"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(bool, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

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

    def get_job_task_sets(
        self,
        fullname: str,
    ) -> list[models.TaskSet]:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/job/task_sets"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.TaskSet], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_job_wms_reports(
        self,
        fullname: str,
    ) -> list[models.WmsTaskReport]:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/job/wms_reports"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.WmsTaskReport], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_job_product_sets(
        self,
        fullname: str,
    ) -> list[models.ProductSet]:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/job/product_sets"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.ProductSet], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_job_errors(
        self,
        fullname: str,
    ) -> list[models.PipetaskError]:
        params = models.FullnameQuery(
            fullname=fullname,
        )
        query = "get/job/errors"
        results = self._client.get(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(list[models.PipetaskError], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def update_status(
        self,
        **kwargs: Any,
    ) -> StatusEnum:
        query = "update/status"
        params = models.UpdateStatusQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(StatusEnum, results["status"])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def update_collections(
        self,
        **kwargs: Any,
    ) -> dict:
        query = "update/collections"
        params = models.UpdateNodeQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(dict, results["collections"])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def update_data_dict(
        self,
        **kwargs: Any,
    ) -> dict:
        query = "update/data_dict"
        params = models.UpdateNodeQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(dict, results["data"])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def update_spec_aliases(
        self,
        **kwargs: Any,
    ) -> dict:
        query = "update/spec_aliases"
        params = models.UpdateNodeQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(dict, results["spec_aliases"])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def update_child_config(
        self,
        **kwargs: Any,
    ) -> dict:
        query = "update/child_config"
        params = models.UpdateNodeQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(dict, results["child_config"])
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def add_groups(
        self,
        **kwargs: Any,
    ) -> list[models.Group]:
        query = "add/groups"
        params = models.AddGroups(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.Group], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def add_steps(
        self,
        **kwargs: Any,
    ) -> list[models.Step]:
        query = "add/steps"
        params = models.AddSteps(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.Step], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def add_campaign(
        self,
        **kwargs: Any,
    ) -> models.Campaign:
        query = "add/campaign"
        params = models.CampaignCreate(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Campaign, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def load_specification(
        self,
        **kwargs: Any,
    ) -> models.Specification:
        query = "load/specification"
        params = models.SpecificationLoad(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Specification, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def load_campaign(
        self,
        **kwargs: Any,
    ) -> models.Campaign:
        query = "load/campaign"
        params = models.LoadAndCreateCampaign(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Campaign, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def load_error_types(
        self,
        **kwargs: Any,
    ) -> list[models.PipetaskErrorType]:
        query = "load/error_types"
        params = models.YamlFileQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.PipetaskErrorType], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def load_manifest_report(
        self,
        **kwargs: Any,
    ) -> models.Job:
        query = "load/manifest_report"
        params = models.LoadManifestReport(**kwargs)
        results = self._client.post(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Job, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def process(
        self,
        **kwargs: Any,
    ) -> StatusEnum:
        query = "actions/process"
        params = models.NodeQuery(**kwargs)
        results = self._client.post(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(StatusEnum, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def retry_script(
        self,
        **kwargs: Any,
    ) -> models.Script:
        query = "actions/retry_script"
        params = models.ScriptQueryBase(**kwargs)
        results = self._client.post(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Script, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def rescue_script(
        self,
        **kwargs: Any,
    ) -> models.Script:
        query = "actions/rescue_script"
        params = models.ScriptQueryBase(**kwargs)
        results = self._client.post(f"{query}", params=params.dict()).json()
        try:
            return parse_obj_as(models.Script, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def mark_script_rescued(
        self,
        **kwargs: Any,
    ) -> list[models.Script]:
        query = "actions/mark_script_rescued"
        params = models.ScriptQueryBase(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.Script], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def rematch_errors(
        self,
        **kwargs: Any,
    ) -> list[models.PipetaskError]:
        query = "actions/rematch_errors"
        params = models.RematchQuery(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.PipetaskError], results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def get_productions(self) -> list[models.Production]:
        productions = []
        params = {"skip": 0}
        query = "productions"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            productions.extend(parse_obj_as(list[models.Production], results))
            params["skip"] += len(results)
        return productions

    def get_campaigns(
        self,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[models.Campaign]:
        campaigns = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        query = "campaigns"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            campaigns.extend(parse_obj_as(list[models.Campaign], results))
            params["skip"] += len(results)
        return campaigns

    def get_steps(
        self,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[models.Step]:
        steps = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        query = "steps"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            steps.extend(parse_obj_as(list[models.Step], results))
            params["skip"] += len(results)
        return steps

    def get_groups(
        self,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[models.Group]:
        groups = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        query = "groups"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            groups.extend(parse_obj_as(list[models.Group], results))
            params["skip"] += len(results)
        return groups

    def get_jobs(
        self,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[models.Job]:
        jobs = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        query = "jobs"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            jobs.extend(parse_obj_as(list[models.Job], results))
            params["skip"] += len(results)
        return jobs

    def get_scripts(
        self,
        parent_id: int | None = None,
        parent_name: str | None = None,
    ) -> list[models.Script]:
        scripts = []
        params: dict[str, Any] = {"skip": 0}
        if parent_id:
            params["parent_id"] = parent_id
        if parent_name:
            params["parent_name"] = parent_name
        query = "scripts"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            scripts.extend(parse_obj_as(list[models.Script], results))
            params["skip"] += len(results)
        return scripts

    def get_specifications(self) -> list[models.Specification]:
        specifications = []
        params = {"skip": 0}
        query = "specifications"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            specifications.extend(parse_obj_as(list[models.Specification], results))
            params["skip"] += len(results)
        return specifications

    def get_spec_blocks(self) -> list[models.SpecBlock]:
        spec_blocks = []
        params = {"skip": 0}
        query = "spec_blocks"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            spec_blocks.extend(parse_obj_as(list[models.SpecBlock], results))
            params["skip"] += len(results)
        return spec_blocks

    def get_script_templates(self) -> list[models.ScriptTemplate]:
        script_templates = []
        params = {"skip": 0}
        query = "script_templates"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            script_templates.extend(parse_obj_as(list[models.ScriptTemplate], results))
            params["skip"] += len(results)
        return script_templates

    def get_pipetask_error_types(self) -> list[models.PipetaskErrorType]:
        pipetask_error_types = []
        params = {"skip": 0}
        query = "pipetask_error_types"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            pipetask_error_types.extend(parse_obj_as(list[models.PipetaskErrorType], results))
            params["skip"] += len(results)
        return pipetask_error_types

    def get_pipetask_errors(self) -> list[models.PipetaskError]:
        pipetask_errors = []
        params = {"skip": 0}
        query = "pipetask_errors"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            pipetask_errors.extend(parse_obj_as(list[models.PipetaskError], results))
            params["skip"] += len(results)
        return pipetask_errors

    def get_script_errors(self) -> list[models.ScriptError]:
        script_errors = []
        params = {"skip": 0}
        query = "script_errors"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            script_errors.extend(parse_obj_as(list[models.ScriptError], results))
            params["skip"] += len(results)
        return script_errors

    def get_task_sets(self) -> list[models.TaskSet]:
        task_sets = []
        params = {"skip": 0}
        query = "task_sets"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            task_sets.extend(parse_obj_as(list[models.TaskSet], results))
            params["skip"] += len(results)
        return task_sets

    def get_product_sets(self) -> list[models.ProductSet]:
        product_sets = []
        params = {"skip": 0}
        query = "product_sets"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            product_sets.extend(parse_obj_as(list[models.ProductSet], results))
            params["skip"] += len(results)
        return product_sets

    def get_wms_task_reports(self) -> list[models.WmsTaskReport]:
        wms_task_reports = []
        params = {"skip": 0}
        query = "wms_task_reports"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            wms_task_reports.extend(parse_obj_as(list[models.WmsTaskReport], results))
            params["skip"] += len(results)
        return wms_task_reports

    def get_script_dependencies(self) -> list[models.Dependency]:
        script_dependencies = []
        params = {"skip": 0}
        query = "script_dependencies"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            script_dependencies.extend(parse_obj_as(list[models.Dependency], results))
            params["skip"] += len(results)
        return script_dependencies

    def get_step_dependencies(self) -> list[models.Dependency]:
        step_dependencies = []
        params = {"skip": 0}
        query = "step_dependencies"
        while (results := self._client.get(f"{query}", params=params).json()) != []:
            step_dependencies.extend(parse_obj_as(list[models.Dependency], results))
            params["skip"] += len(results)
        return step_dependencies

    def production_create(self, **kwargs: Any) -> models.Production:
        query = "productions"
        params = models.ProductionCreate(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Production, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def production_update(
        self,
        row_id: int,
        **kwargs: Any,
    ) -> models.Production:
        query = f"productions/{row_id}"
        params = models.Production(id=row_id, **kwargs)
        results = self._client.put(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Production, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def production_delete(
        self,
        row_id: int,
    ) -> None:
        query = f"productions/{row_id}"
        self._client.delete(f"{query}")

    def campaign_create(self, **kwargs: Any) -> models.Campaign:
        query = "campaigns"
        params = models.CampaignCreate(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Campaign, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def campaign_update(
        self,
        row_id: int,
        **kwargs: Any,
    ) -> models.Campaign:
        query = f"campaigns/{row_id}"
        params = models.Campaign(id=row_id, **kwargs)
        results = self._client.put(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(models.Campaign, results)
        except ValidationError as msg:
            raise ValueError(f"Bad response: {results}") from msg

    def campaign_delete(
        self,
        row_id: int,
    ) -> None:
        query = f"campaigns/{row_id}"
        self._client.delete(f"{query}")
