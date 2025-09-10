from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class ClientCookie(BaseModel):
    name: str
    value: str


class ClientConfiguration(BaseSettings):
    """Configuration for cm-client."""

    model_config = SettingsConfigDict(
        env_prefix="CM_",
        case_sensitive=False,
        extra="ignore",
        env_file="~/.cm-client",
        env_file_encoding="utf-8",
    )

    server_port: int = Field(
        default=18080,
        description="Port for the frontend WebUI to bind",
    )

    base_url: str = Field(
        default="http://localhost:8080/cm-service",
        description="Base URL for the CM Service API",
        validation_alias="CM_ENDPOINT",
    )

    api_version: str = Field(
        default="v2",
        description="Version of the CM Service API",
    )

    auth_token: str | None = Field(
        default=None,
        validation_alias="CM_TOKEN",
    )

    cookies: list[ClientCookie] | None = Field(
        description=(
            "Comma separated list of pipe-separated cookie names and values, e.g., `name|value,name|value`"
        ),
        default=None,
        validation_alias="CM_COOKIES",
    )

    timeout: float = Field(
        default=30.0,
        validation_alias="CM_TIMEOUT",
    )

    @field_validator("cookies", mode="before", check_fields=True)
    @classmethod
    def validate_cookies(cls, v: Any) -> list[ClientCookie] | None:
        if v is None:  # pragma: no cover
            return v
        return [ClientCookie(name=n, value=v) for n, v in [a.split("|") for a in v.split(",")]]


settings = ClientConfiguration()
"""Configuration for cm-client."""
