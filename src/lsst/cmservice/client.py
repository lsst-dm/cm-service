import httpx
from pydantic import parse_obj_as

from . import models

__all__ = ["CMClient"]


class CMClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, url: str) -> None:
        self._client = httpx.Client(base_url=url)

    def get_productions(self) -> list[models.Production]:
        skip = 0
        productions = []
        query = "productions?"
        while (results := self._client.get(f"{query}skip={skip}").json()) != []:
            productions.extend(parse_obj_as(list[models.Production], results))
            skip += len(results)
        return productions

    def get_campaigns(self, production: int | None = None) -> list[models.Campaign]:
        skip = 0
        campaigns = []
        query = f"campaigns?{f'production={production}&' if production else ''}"
        while (results := self._client.get(f"{query}skip={skip}").json()) != []:
            campaigns.extend(parse_obj_as(list[models.Campaign], results))
            skip += len(results)
        return campaigns

    def get_steps(self, campaign: int | None = None) -> list[models.Step]:
        skip = 0
        steps = []
        query = f"steps?{f'campaign={campaign}&' if campaign else ''}"
        while (results := self._client.get(f"{query}skip={skip}").json()) != []:
            steps.extend(parse_obj_as(list[models.Step], results))
            skip += len(results)
        return steps

    def get_groups(self, step: int | None = None) -> list[models.Group]:
        skip = 0
        groups = []
        query = f"groups?{f'step={step}&' if step else ''}"
        while (results := self._client.get(f"{query}skip={skip}").json()) != []:
            groups.extend(parse_obj_as(list[models.Group], results))
            skip += len(results)
        return groups
