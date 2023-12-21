"""Top level for python client API"""
from __future__ import annotations

import httpx

from .actions import CMActionClient
from .adders import CMAddClient
from .campaigns import CMCampaignClient
from .groups import CMGroupClient
from .jobs import CMJobClient
from .loaders import CMLoadClient
from .pipetask_error_types import CMPipetaskErrorTypeClient
from .pipetask_errors import CMPipetaskErrorClient
from .product_sets import CMProductSetClient
from .productions import CMProductionClient
from .queries import CMQueryClient
from .queues import CMQueueClient
from .script_dependencies import CMScriptDependencyClient
from .script_errors import CMScriptErrorClient
from .script_template_associations import CMScriptTemplateAssociationClient
from .script_templates import CMScriptTemplateClient
from .scripts import CMScriptClient
from .spec_block_associations import CMSpecBlockAssociationClient
from .spec_blocks import CMSpecBlockClient
from .specifications import CMSpecificationClient
from .step_dependencies import CMStepDependencyClient
from .steps import CMStepClient
from .task_sets import CMTaskSetClient
from .wms_task_reports import CMWmsTaskReportClient

__all__ = ["CMClient"]


class CMClient:  # pylint: disable=too-many-instance-attributes
    """Interface for accessing remote cm-service."""

    def __init__(self: CMClient, url: str) -> None:
        self._client = httpx.Client(base_url=url)
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

        self.script_template_association = CMScriptTemplateAssociationClient(self)
        self.spec_block_association = CMSpecBlockAssociationClient(self)
        self.script_dependency = CMScriptDependencyClient(self)
        self.step_dependency = CMStepDependencyClient(self)

        self.query = CMQueryClient(self)
        self.action = CMActionClient(self)
        self.add = CMAddClient(self)
        self.load = CMLoadClient(self)

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client
