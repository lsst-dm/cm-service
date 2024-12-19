from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Configuration", "config"]


class HTCondorConfiguration(BaseModel):
    """Configuration settings for htcondor client operations.

    Set via HTCONDOR__FIELD environment variables.
    """

    condor_submit_bin: str = Field(
        description="Name of condor_submit client binary",
        default="condor_submit",
    )

    condor_q_bin: str = Field(
        description="Name of condor_q client binary",
        default="condor_q",
    )

    request_cpus: int = Field(
        description="Number of cores to request when submitting an htcondor job.",
        default=1,
    )

    request_mem: str = Field(
        description="Amount of memory requested when submitting an htcondor job.",
        default="512M",
    )

    request_disk: str = Field(
        description="Amount of disk space requested when submitting an htcondor job.",
        default="1G",
    )


class SlurmConfiguration(BaseModel):
    """Configuration settings for slurm client operations.

    Set via SLURM__FIELD environment variables.

    Note
    ----
    Default SBATCH_* variables could work just as well, but it is useful to
    have this as a document of what settings are actually used.
    """

    sacct_bin: str = Field(
        description="Name of sacct slurm client binary",
        default="sacct",
    )

    sbatch_bin: str = Field(
        description="Name of sbatch slurm client binary",
        default="sbatch",
    )

    memory: str = Field(
        description="Amount of memory requested when submitting a slurm job.",
        default="16448",
    )

    account: str = Field(
        description="Account used when submitting a slurm job.",
        default="rubin:production",
    )

    partition: str = Field(
        description="Partition requested when submitting a slurm job.",
        default="milano",
    )


class AsgiConfiguration(BaseModel):
    """Configuration for the application's ASGI web server."""

    title: str = Field(
        description="Title of the ASGI application",
        default="cm-service",
    )

    host: str = Field(
        description="The host address to which the asgi server should bind",
        default="0.0.0.0",
    )

    port: int = Field(
        description="Port number for the asgi server to listen on",
        default=8080,
    )

    prefix: str = Field(
        description="The URL prefix for the cm-service API",
        default="/cm-service/v1",
    )

    frontend_prefix: str = Field(
        description="The URL prefix for the frontend web app",
        default="/web_app",
    )


class LoggingConfiguration(BaseModel):
    """Configuration for the application's logging facility."""

    level: str = Field(
        default="INFO",
        title="Log level of the application's logger",
    )

    profile: str = Field(
        default="development",
        title="Application logging profile",
    )


class DatabaseConfiguration(BaseModel):
    """Database configuration nested model.

    Set according to DB__FIELD environment variables.
    """

    url: str = Field(
        default="",
        description="The URL for the cm-service database",
    )

    password: str | None = Field(
        default=None,
        description="The password for the cm-service database",
    )

    table_schema: str | None = Field(
        default=None,
        description="Schema to use for cm-service database",
    )

    echo: bool = Field(
        default=False,
        description="SQLAlchemy engine echo setting for the cm-service database",
    )


class Configuration(BaseSettings):
    """Configuration for cm-service.

    Nested models may be consumed from environment variables named according to
    the pattern 'NESTED_MODEL__FIELD' or via any `validation_alias` applied to
    a field.
    """

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        nested_model_default_partial_update=True,
        case_sensitive=False,
        extra="ignore",
    )

    # Nested Models
    asgi: AsgiConfiguration = AsgiConfiguration()
    db: DatabaseConfiguration = DatabaseConfiguration()
    htcondor: HTCondorConfiguration = HTCondorConfiguration()
    logging: LoggingConfiguration = LoggingConfiguration()
    slurm: SlurmConfiguration = SlurmConfiguration()


config = Configuration()
"""Configuration for cm-service."""
