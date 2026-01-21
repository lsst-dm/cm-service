import typer
from pydantic import BaseModel

from .settings import settings


class AppContext(BaseModel):
    auth_token: str = settings.token
    campaign_name: str | None = None
    campaign_id: str | None = None
    endpoint_url: str = settings.endpoint
    output_format: str
    api_version: str = settings.api_version


class TypedContext(typer.Context):
    obj: AppContext
