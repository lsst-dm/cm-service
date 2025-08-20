import os
from enum import IntFlag, auto
from functools import reduce
from typing import Any

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Features(IntFlag):
    """A flag enum for setting specific application behaviors through feature
    flags.
    """

    API_V1 = auto()
    API_V2 = auto()
    DAEMON_CAMPAIGNS = auto()
    DAEMON_NODES = auto()
    DAEMON_V1 = auto()
    DAEMON_V2 = auto()
    WEBAPP_V1 = auto()
    STORE_FSM = auto()
    ALLOW_TASK_UPSERT = auto()
    MOCK_BUTLER = auto()


class EnabledFeatures(BaseSettings):
    """Pydantic Settings class for managing the enabled features of an
    application."""

    model_config = SettingsConfigDict(
        env_prefix="FEATURE_",
        case_sensitive=False,
        extra="allow",
    )

    enabled: Features = Field(
        description="A Flag Enum for enabled application features.", default=Features(0)
    )

    @field_validator("enabled")
    @classmethod
    def determine_enabled_features(cls, data: Any, info: ValidationInfo) -> Any:
        """Check all environment variables according to the `env_prefix` of the
        model config and set/unset feature flags for the matching feature.
        """
        if (env_prefix := cls.model_config.get("env_prefix")) is None:
            return data
        enabled = set()
        disabled = set()
        for feature_env_var in filter(lambda k: k.startswith(env_prefix), os.environ.keys()):
            try:
                if os.getenv(feature_env_var, "false").strip().lower() in ("1", "t", "true", "yes", "on"):
                    enabled.add(Features[feature_env_var.replace(env_prefix, "")])
                else:
                    disabled.add(Features[feature_env_var.replace(env_prefix, "")])
            except KeyError:
                # no matching feature
                pass

        data = reduce(lambda x, y: x | y, enabled, data)
        data = reduce(lambda x, y: x & ~y, disabled, data)
        return data
