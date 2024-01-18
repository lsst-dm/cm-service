from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient


class CMLoadClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    specification = wrappers.get_general_post_function(
        models.SpecificationLoad,
        models.Specification,
        "load/specification",
    )

    campaign = wrappers.get_general_post_function(
        models.LoadAndCreateCampaign,
        models.Campaign,
        "load/campaign",
    )

    error_types = wrappers.get_general_post_function(
        models.YamlFileQuery,
        list[models.PipetaskErrorType],
        "load/error_types",
    )

    manifest_report = wrappers.get_general_post_function(
        models.LoadManifestReport,
        models.Job,
        "load/manifest_report",
    )
