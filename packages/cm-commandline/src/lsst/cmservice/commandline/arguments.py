from typing import Annotated, Literal
from uuid import UUID, uuid5

import typer

from .settings import settings


def preprocess_campaign_name(campaign: str) -> str:
    """Preprocesses a campaign NAME by translating it to a campaign ID"""
    try:
        campaign_id = UUID(campaign)
        return str(campaign_id)
    except ValueError:
        return str(uuid5(settings.default_namespace, campaign))


campaign_name = Annotated[str, typer.Argument()]

campaign_id = Annotated[str, typer.Argument(envvar="CM_CAMPAIGN", callback=preprocess_campaign_name)]

campaign_status = Annotated[
    Literal["paused", "rejected", "accepted", "failed"], typer.Argument(help="Campaign status name")
]

node_id = Annotated[str, typer.Argument()]
