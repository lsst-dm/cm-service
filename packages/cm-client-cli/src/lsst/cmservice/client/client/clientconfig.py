from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ClientConfiguration", "client_config"]


class ClientCookie(BaseModel):
    name: str
    value: str


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

    cookies: list[ClientCookie] | None = Field(
        description=(
            "Comma separated list of pipe-separated cookie names and values, e.g., `name|value,name|value`"
        ),
        default=None,
        validation_alias="CM_COOKIES",
    )

    timeout: float | None = Field(
        default=None,
        validation_alias="CM_TIMEOUT",
    )

    # Field validator to convert empty string, 'null', or 'None' to actual None
    @field_validator("timeout", mode="before", check_fields=True)
    @classmethod
    def validate_timeout(cls, v: Any) -> float | None:
        if isinstance(v, str) and v in {"", "null", "None"}:  # pragma: no cover
            return None
        return v

    @field_validator("cookies", mode="before", check_fields=True)
    @classmethod
    def validate_cookies(cls, v: Any) -> list[ClientCookie] | None:
        if v is None:  # pragma: no cover
            return v
        return [ClientCookie(name=n, value=v) for n, v in [a.split("|") for a in v.split(",")]]


client_config = ClientConfiguration()
"""Configuration for cm-client."""
