"""Top level for python client API"""

from __future__ import annotations

from typing import Any

import httpx

from .actions import CMActionClient
from .adders import CMAddClient
from .campaigns import CMCampaignClient
from .clientconfig import client_config
from .groups import CMGroupClient
from .jobs import CMJobClient
from .loaders import CMLoadClient
from .pipetask_error_types import CMPipetaskErrorTypeClient
from .pipetask_errors import CMPipetaskErrorClient
from .product_sets import CMProductSetClient
from .productions import CMProductionClient
from .queues import CMQueueClient
from .script_dependencies import CMScriptDependencyClient
from .script_errors import CMScriptErrorClient
from .script_templates import CMScriptTemplateClient
from .scripts import CMScriptClient
from .spec_blocks import CMSpecBlockClient
from .specifications import CMSpecificationClient
from .step_dependencies import CMStepDependencyClient
from .steps import CMStepClient
from .task_sets import CMTaskSetClient
from .wms_task_reports import CMWmsTaskReportClient

__all__ = ["CMClient"]


class CMClient:  # pylint: disable=too-many-instance-attributes
    """Interface for accessing remote cm-service."""

    def __init__(self: CMClient) -> None:
        client_kwargs: dict[str, Any] = {}
        client_kwargs["base_url"] = client_config.service_url
        if "auth_token" in client_config.model_fields_set:
            client_kwargs["headers"] = {"Authorization": f"Bearer {client_config.auth_token}"}
        if "timeout" in client_config.model_fields_set:
            client_kwargs["timeout"] = client_config.timeout
        self._client = httpx.Client(**client_kwargs)

        self.production = CMProductionClient(self)
        self.campaign = CMCampaignClient(self)
        self.step = CMStepClient(self)
        self.group = CMGroupClient(self)
        self.job = CMJobClient(self)
        self.script = CMScriptClient(self)
        self.queue = CMQueueClient(self)

        self.specification = CMSpecificationClient(self)
        self.spec_block = CMSpecBlockClient(self)
        self.script_template = CMScriptTemplateClient(self)

        self.pipetask_error_type = CMPipetaskErrorTypeClient(self)
        self.pipetask_error = CMPipetaskErrorClient(self)
        self.script_error = CMScriptErrorClient(self)

        self.product_set = CMProductSetClient(self)
        self.task_set = CMTaskSetClient(self)
        self.wms_task_report = CMWmsTaskReportClient(self)

        self.script_dependency = CMScriptDependencyClient(self)
        self.step_dependency = CMStepDependencyClient(self)

        self.action = CMActionClient(self)
        self.add = CMAddClient(self)
        self.load = CMLoadClient(self)

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client
