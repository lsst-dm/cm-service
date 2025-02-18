from warnings import warn

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .common.enums import ScriptMethodEnum, StatusEnum, WmsComputeSite

__all__ = ["Configuration", "config"]

load_dotenv()


class BpsConfiguration(BaseModel):
    """Configuration settings for bps client operations.

    Set via BPS__FIELD environment variables.

    FIXME: rename to LsstConfiguration and consolidate multiple models?
    """

    lsst_version: str = Field(
        description="Default LSST version",
        default="w_latest",
    )

    lsst_distrib_dir: str = Field(
        description="Default distribution directory from which to setup lsst",
        default="/sdf/group/rubin/sw",
    )

    bps_bin: str = Field(
        description="Name of a bps client binary",
        default="bps",
    )

    pipetask_bin: str = Field(
        description="Name of a pipetask client binary",
        default="pipetask",
    )

    resource_usage_bin: str = Field(
        description="Name of a resource usage gathering binary",
        default="build-gather-resource-usage-qg",
    )

    n_jobs: int = Field(
        description="Parallelization factor for jobs (-j N)",
        default=16,
    )


class ButlerConfiguration(BaseModel):
    """Configuration settings for butler client operations.

    Set via BUTLER__FIELD environment variables.
    """

    butler_bin: str = Field(
        description="Name of a butler client binary",
        default="butler",
    )

    repository_index: str = Field(
        description="Fully qualified path to a butler repository index.",
        default="/sdf/group/rubin/shared/data-repos.yaml",
    )

    authentication_file: str = Field(
        description="Path and name of a db-auth.yaml to use with Butler",
        default="~/.lsst/db-auth.yaml",
    )

    default_username: str = Field(
        description="Default username to use for Butler registry authentication",
        default="rubin",
    )

    mock: bool = Field(
        description="Whether to mock out Butler calls.",
        default=False,
    )


class HipsConfiguration(BaseModel):
    """Configuration settings for HiPS operations.

    Set via HIPS__FIELD environment variables.
    """

    high_res_bin: str = Field(
        description="Name of a high resolution QG builder bin",
        default="build-high-resolution-hips-qg",
    )

    uri: str = Field(
        description="URI for HiPS maps destination",
        default="s3://rubin-hips",
    )


class HTCondorConfiguration(BaseModel):
    """Configuration settings for htcondor client operations.

    Set via HTCONDOR__FIELD environment variables.

    Fields with `exclude=True` are not included when a `model_dump` is called
    on this model; included fields will be represented by their field name or
    their serialization alias.
    """

    config_source: str = Field(
        description="Source of htcondor configuration",
        default="ONLY_ENV",
        serialization_alias="CONDOR_CONFIG",
    )

    remote_user_home: str = Field(
        description=("Path to the user's home directory, as resolvable from an htcondor access node."),
        default="/sdf/home/l/lsstsvc1",
        exclude=True,
    )

    condor_home: str = Field(
        description=("Path to the Condor home directory. Equivalent to the condor ``RELEASE_DIR`` macro."),
        default="/opt/htcondor",
        serialization_alias="_CONDOR_RELEASE_DIR",
    )

    # TODO retire these in favor of a path relative to condor_home
    condor_submit_bin: str = Field(
        description="Name of condor_submit client binary",
        default="condor_submit",
        exclude=True,
    )

    condor_q_bin: str = Field(
        description="Name of condor_q client binary",
        default="condor_q",
        exclude=True,
    )

    universe: str = Field(
        description="HTCondor Universe into which a job will be submitted.",
        default="vanilla",
        serialization_alias="_CONDOR_DEFAULT_UNIVERSE",
    )

    working_directory: str = Field(
        description=(
            "Path to a working directory to use when submitting condor jobs. "
            "This path must be available to both the submitting service and "
            "the access point receiving the job. Corresponds to the "
            "`initialdir` submit file command."
        ),
        default=".",
        exclude=True,
    )

    batch_name: str = Field(
        description=(
            "Name to use in identifying condor jobs. Corresponds to "
            "the `condor_submit` `-batch-name` parameter or submit file "
            "`batch_name` command."
        ),
        default="usdf-cm-dev",
        exclude=True,
    )

    request_cpus: int = Field(
        description="Number of cores to request when submitting an htcondor job.",
        default=1,
        exclude=True,
    )

    request_mem: str = Field(
        description="Amount of memory requested when submitting an htcondor job.",
        default="512M",
        exclude=True,
    )

    request_disk: str = Field(
        description="Amount of disk space requested when submitting an htcondor job.",
        default="1G",
        exclude=True,
    )

    collector_host: str = Field(
        description="Name of an htcondor collector host.",
        default="localhost",
        serialization_alias="_CONDOR_COLLECTOR_HOST",
    )

    schedd_host: str = Field(
        description="Name of an htcondor schedd host.",
        default="localhost",
        serialization_alias="_CONDOR_SCHEDD_HOST",
    )

    authn_methods: str = Field(
        description="Secure client authentication methods, as comma-delimited strings",
        default="FS_REMOTE",
        serialization_alias="_CONDOR_SEC_CLIENT_AUTHENTICATION_METHODS",
    )

    fs_remote_dir: str = Field(
        description="Shared directory to use with htcondor remote filesystem authentication.",
        default="/tmp",
        serialization_alias="FS_REMOTE_DIR",
    )


# TODO deprecate and remove "slurm"-specific logic from cm-service; it is
#      unlikely that interfacing with slurm directly from k8s will be possible.
class SlurmConfiguration(BaseModel):
    """Configuration settings for slurm client operations.

    Set via SLURM__FIELD environment variables.

    Note
    ----
    Default SBATCH_* variables could work just as well, but it is useful to
    have this as a document of what settings are actually used.

    These settings should also apply to htcondor resource allocation jobs
    that are equivalent to "allocateNodes"
    """

    home: str = Field(
        description="Location of the installed slurm client binaries",
        default="/opt/slurm/slurm-curr/bin",
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

    platform: str = Field(
        description="Platform requested when submitting a slurm job.",
        default="s3df",
    )

    duration: str = Field(
        description="Expected Duration for a cmservice script that needs to be scheduled.",
        default="0-1:0:0",
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
        default="/cm-service",
    )

    frontend_prefix: str = Field(
        description="The URL prefix for the frontend web app",
        default="/web_app",
    )

    reload: bool = Field(
        description="Whether to support ASGI server reload on content change.",
        default=False,
    )


class LoggingConfiguration(BaseModel):
    """Configuration for the application's logging facility."""

    handle: str = Field(
        default="cm-service",
        title="Handle or name of the root logger",
    )

    level: str = Field(
        default="INFO",
        title="Log level of the application's logger",
    )

    profile: str = Field(
        default="development",
        title="Application logging profile",
    )


class DaemonConfiguration(BaseModel):
    """Settings for the Daemon nested model.

    Set according to DAEMON__FIELD environment variables.
    """

    allocate_resources: bool = Field(
        default=False,
        description="Whether the daemon should try to allocate its own htcondor or slurm resources.",
    )

    processing_interval: int = Field(
        default=30,
        description=(
            "The maximum wait time (seconds) between daemon processing intervals "
            "and the minimum time between element processing attepts. This "
            "duration may be lengthened depending on the element type."
        ),
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
    bps: BpsConfiguration = BpsConfiguration()
    butler: ButlerConfiguration = ButlerConfiguration()
    daemon: DaemonConfiguration = DaemonConfiguration()
    db: DatabaseConfiguration = DatabaseConfiguration()
    hips: HipsConfiguration = HipsConfiguration()
    htcondor: HTCondorConfiguration = HTCondorConfiguration()
    logging: LoggingConfiguration = LoggingConfiguration()
    slurm: SlurmConfiguration = SlurmConfiguration()

    # Root fields
    script_handler: ScriptMethodEnum = Field(
        description="The default external script handler",
        default=ScriptMethodEnum.htcondor,
    )

    compute_site: WmsComputeSite = Field(
        description="The default WMS compute site",
        default=WmsComputeSite.usdf,
    )

    mock_status: StatusEnum | None = Field(
        description="A fake status to return from all operations",
        default=None,
    )

    @field_validator("mock_status", mode="before")
    @classmethod
    def validate_mock_status_by_name(cls, value: str | StatusEnum) -> StatusEnum | None:
        if isinstance(value, StatusEnum) or value is None:
            return value
        try:
            return StatusEnum[value]
        except KeyError:
            warn(f"Invalid mock status ({value}) provided to config, using default.")
            return None

    # TODO refactor these identical field validators with type generics
    @field_validator("script_handler", mode="before")
    @classmethod
    def validate_script_method_by_name(cls, value: str | ScriptMethodEnum) -> ScriptMethodEnum:
        """Use a string value to resolve an enum by its name, falling back to
        the default value if an invalid input is provided.
        """
        if isinstance(value, ScriptMethodEnum):
            return value
        try:
            return ScriptMethodEnum[value]
        except KeyError:
            warn(f"Invalid script handler ({value}) provided to config, using default.")
            return ScriptMethodEnum.htcondor

    @field_validator("compute_site", mode="before")
    @classmethod
    def validate_compute_site_by_name(cls, value: str | WmsComputeSite) -> WmsComputeSite:
        """Use a string value to resolve an enum by its name, falling back to
        the default value if an invalid input is provided.
        """
        if isinstance(value, WmsComputeSite):
            return value
        try:
            return WmsComputeSite[value]
        except KeyError:
            warn(f"Invalid script handler ({value}) provided to config, using default.")
            return WmsComputeSite.usdf


config = Configuration()
"""Configuration for cm-service."""
