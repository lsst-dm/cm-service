import re
from typing import Annotated, Literal
from uuid import uuid5

import typer

from .models import TypedContext
from .settings import settings


def as_snake_case(s: str) -> str:
    """Preprocesses a string by sanitizing it and producing snake case."""
    # TODO clean up unicode characters and etc
    return re.sub(r"\W+?", "_", s)


def preprocess_campaign_name(ctx: TypedContext, campaign: str) -> str:
    """Preprocesses a campaign NAME by translating it to a campaign ID and
    storing the result in the application context
    """
    ctx.obj.campaign_name = campaign
    ctx.obj.campaign_id = str(uuid5(settings.default_namespace, campaign))
    return campaign


campaign_name = Annotated[
    str,
    typer.Argument(
        envvar="CM_CAMPAIGN",
        callback=preprocess_campaign_name,
        help="A campaign name that is coerced into a UUID, or a UUID.",
    ),
]


campaign_status = Annotated[
    Literal["paused", "rejected", "accepted", "failed"], typer.Argument(help="Campaign status name")
]


node_id = Annotated[str, typer.Argument(help="An id for a node, as a UUID value.")]
