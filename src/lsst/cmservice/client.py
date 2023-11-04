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

    def get_scripts(
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

    def get_jobs(
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
        query = "get/jobs"
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
    ) -> list[models.Group]:
        query = "add/groups"
        params = models.AddSteps(**kwargs)
        results = self._client.post(f"{query}", content=params.json()).json()
        try:
            return parse_obj_as(list[models.Group], results)
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
