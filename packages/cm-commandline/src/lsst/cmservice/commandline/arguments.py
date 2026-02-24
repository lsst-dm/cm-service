import re
from typing import Annotated, Literal
from uuid import UUID, uuid5

import typer

from .models import TypedContext
from .settings import settings


def as_snake_case(s: str) -> str:
    """Preprocesses a string by sanitizing it and producing snake case."""
    # TODO clean up unicode characters and etc
    return re.sub(r"\W+?", "_", s)


def preprocess_campaign_name(ctx: TypedContext, campaign: str | None) -> str | None:
    """Preprocesses a campaign NAME by translating it to a campaign ID and
    storing the result in the application context
    """
    if campaign is None:
        return campaign
    try:
        campaign_id = UUID(campaign)
        ctx.obj.campaign_name = str(campaign_id)
        ctx.obj.campaign_id = str(campaign_id)
        sanitized_campaign_name = campaign
    except ValueError:
        sanitized_campaign_name = as_snake_case(campaign)
        ctx.obj.campaign_name = sanitized_campaign_name
        ctx.obj.campaign_id = str(uuid5(settings.default_namespace, sanitized_campaign_name))
    return sanitized_campaign_name


class CampaignName:
    """An argument representing a campaign name that may be used by multiple
    commands.
    """

    _config = {
        "envvar": "CM_CAMPAIGN",
        "callback": preprocess_campaign_name,
        "help": "A campaign name that is coerced into a UUID, or a UUID",
    }
    Required = Annotated[str, typer.Argument(**_config)]
    Optional = Annotated[str | None, typer.Argument(**_config)]


campaign_status = Annotated[
    Literal["paused", "rejected", "accepted", "failed"], typer.Argument(help="Campaign status name")
]


node_id = Annotated[str, typer.Argument(help="An id for a node, as a UUID value.")]
