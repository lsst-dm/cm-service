from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CM_",
        case_sensitive=False,
        extra="ignore",
        env_file="~/.cm-client",
        env_file_encoding="utf-8",
    )

    default_namespace: UUID = Field(
        default=UUID("dda54a0c-6878-5c95-ac4f-007f6808049e"),
        description="Default namespace UUID for campaigns",
    )

    endpoint: str = Field(
        default="http://localhost:8080/cm-service",
        description="Base URL for the CM Service API",
    )

    api_version: str = Field(
        default="v2",
        description="Version of the CM Service API",
    )

    token: str = Field(
        default="",
        description="Gafaelfawr auth token to use with API",
    )


settings = Settings()
