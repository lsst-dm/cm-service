from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ClientConfiguration", "client_config"]


class ClientConfiguration(BaseSettings):
    """Configuration for cm-client."""

    model_config = SettingsConfigDict(env_file="~/.cm-client", env_file_encoding="utf-8")

    service_url: str = Field(
        default="http://localhost:8080/cm-service/v1",
        validation_alias="CM_SERVICE",
    )

    auth_token: str | None = Field(
        default=None,
        validation_alias="CM_TOKEN",
    )


client_config = ClientConfiguration()
"""Configuration for cm-client."""
