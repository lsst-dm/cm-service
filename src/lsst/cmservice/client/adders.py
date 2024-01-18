from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from .. import models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient


class CMAddClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        return self._client

    groups = wrappers.get_general_post_function(models.AddGroups, list[models.Group], "add/groups")

    steps = wrappers.get_general_post_function(models.AddSteps, list[models.Step], "add/steps")

    campaign = wrappers.get_general_post_function(models.CampaignCreate, models.Campaign, "add/campaign")
