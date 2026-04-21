from pathlib import Path
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

    # FIXME add a validator to strip any trailing `/` from value
    base_url: str = Field(
        default="http://localhost:8080/cm-service",
        description="Base URL for the CM Service API",
        validation_alias="CM_ENDPOINT",
    )

    root_path: str = Field(
        default="",
        description="Set the ASGI root path when mounted at a subpath.",
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
        description="Page response timeout",
    )

    static_dir: Path = Field(
        default=Path(__file__).parent / "static",
        description="Filesystem path for static content.",
        validation_alias="CM_STATIC_CONTENT_DIR",
    )

    static_endpoint: str = Field(
        default="/static",
        description="URL endpoint for static files",
    )

    production: bool = Field(
        default=False,
        description="Whether to run the gui in 'production' mode",
    )

    storage_secret: str = Field(
        default="justbetweenyouandme",
        validation_alias="CM_STORAGE_SECRET_KEY",
    )

    reconnect_timeout: float = Field(
        default=30.0,
        validation_alias="CM_RECONNECT_TIMEOUT",
        description="Websocket reconnection timeout. Set higher for networks with high latency or when "
        "debugging clients.",
    )

    max_upload_size: int = Field(
        default=65_535,
        description="""Maximum size in bytes to allow via the Import function.""",
    )

    @field_validator("cookies", mode="before", check_fields=True)
    @classmethod
    def validate_cookies(cls, v: Any) -> list[ClientCookie] | None:
        if v is None:  # pragma: no cover
            return v
        return [ClientCookie(name=n, value=v) for n, v in [a.split("|") for a in v.split(",")]]


settings = ClientConfiguration()
"""Configuration for cm-client."""
