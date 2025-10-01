import logging
from datetime import UTC, datetime
from typing import Annotated, Self
from urllib.parse import urlparse
from warnings import warn

from dotenv import load_dotenv
from pydantic import (
    AliasChoices,
    BaseModel,
    BeforeValidator,
    Field,
    SecretStr,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .common.enums import ScriptMethodEnum, StatusEnum, WmsComputeSite
from .common.flags import EnabledFeatures
from .common.logging import LOGGER_SETTINGS, LoggingConfiguration

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

    artifact_path: str = Field(
        description="Filesystem path location for writing artifacts (`prod_area`)",
        default="/prod_area",
    )

    log_level: Annotated[
        int, BeforeValidator(lambda v: getattr(logging, v.upper()) if isinstance(v, str) else v)
    ] = Field(default=logging.ERROR, title="BPS Log level", description="Logging level for the bps packages.")


class ButlerConfiguration(BaseModel):
    """Configuration settings for butler client operations.

    Set via BUTLER__FIELD environment variables.
    """

    butler_bin: str = Field(
        description="Name of a butler client binary",
        default="butler",
    )

    # FIXME this index is used to hydrate a WMS submission environment, so it
    #       is not used by CM Service to construct Butlers, and may be variable
    #       between sites, so should be relocated to a facility-specific config
    repository_index: str = Field(
        description="Fully qualified path to a butler repository index.",
        default="/sdf/group/rubin/shared/data-repos.yaml",
    )

    authentication_file: str = Field(
        description="Path and name of a db-auth.yaml to use with Butler",
        default="~/.lsst/db-auth.yaml",
    )

    # FIXME this username is probably not necessary to track on its own, as it
    #       should be part of any db authentication scheme associated with
    #       butler use.
    default_username: str = Field(
        description="Default username to use for Butler registry authentication",
        default="rubin",
    )

    eager: bool = Field(
        description="Whether to eagerly instantiate known Butlers at Factory startup",
        default=True,
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


class PandaConfiguration(BaseModel, validate_assignment=True):
    """Configuration parameters for the PanDA WMS"""

    tls_url: str | None = Field(
        description="Base HTTPS URL of PanDA server",
        serialization_alias="PANDA_URL_SSL",
        default=None,
    )

    url: str | None = Field(
        description="Base HTTP URL of PanDA server",
        serialization_alias="PANDA_URL",
        default=None,
    )

    monitor_url: str | None = Field(
        description="URL of PanDA monitor",
        serialization_alias="PANDAMON_URL",
        default=None,
    )

    cache_url: str | None = Field(
        description="Base URL of PanDA sandbox server",
        serialization_alias="PANDACACHE_URL",
        default=None,
    )

    virtual_organization: str = Field(
        description="Virtual organization name used with Panda OIDC",
        serialization_alias="PANDA_AUTH_VO",
        default="Rubin",
    )

    renew_after: int = Field(
        description="Minimum auth token lifetime in seconds before renewal attempts are made",
        default=302_400,
        exclude=True,
    )

    # The presence of this environment variable should cause the panda client
    # to use specified token directly, skipping IO related to reading a token
    # file.
    id_token: str | None = Field(
        description="Current id token for PanDA authentication",
        serialization_alias="PANDA_AUTH_ID_TOKEN",
        default=None,
    )

    refresh_token: str | None = Field(
        description="Current refresh token for PanDA token operations",
        default=None,
        exclude=True,
    )

    token_expiry: datetime | None = Field(
        description="Time at which the current idtoken expires",
        default=None,
        exclude=True,
    )

    config_root: str = Field(
        description="Location of the PanDA .token file",
        serialization_alias="PANDA_CONFIG_ROOT",
        default="/var/run/secrets/panda",
        exclude=True,
    )

    auth_type: str = Field(
        description="Panda Auth type",
        serialization_alias="PANDA_AUTH",
        default="oidc",
    )

    behind_lb: bool = Field(
        description="Whether Panda is behind a loadbalancer",
        default=False,
        serialization_alias="PANDA_BEHIND_REAL_LB",
    )

    verify_host: bool = Field(
        description="Whether to verify PanDA host TLS",
        default=True,
        serialization_alias="PANDA_VERIFY_HOST",
    )

    use_native_httplib: bool = Field(
        description="Use native http lib instead of curl",
        default=True,
        serialization_alias="PANDA_USE_NATIVE_HTTPLIB",
    )

    @computed_field(repr=False)  # type: ignore[prop-decorator]
    @property
    def auth_config_url(self) -> str | None:
        """Location of auth config for PanDA VO."""
        if self.tls_url is None:
            return None
        url_parts = urlparse(self.tls_url)
        return f"{url_parts.scheme}://{url_parts.hostname}:{url_parts.port}/auth/{self.virtual_organization}_auth_config.json"

    @model_validator(mode="after")
    def set_base_url_fields(self) -> Self:
        """Set all url fields when only a subset of urls are supplied."""
        # NOTE: there is a danger of this validator creating a recursion error
        #       if unbounded field-setters are used. Every update to the model
        #       will itself trigger this validator because of the
        #       `validate_assignment` directive on the model itself.

        # If no panda urls have been specified there is no need to continue
        # with model validation
        if self.url is None and self.tls_url is None:
            return self
        # It does not seem critical that these URLs actually use the scheme
        # with which they are nominally associated, only that both be set.
        elif self.url is None:
            self.url = self.tls_url
        elif self.tls_url is None:
            self.tls_url = self.url

        # default the cache url to the tls url
        if self.cache_url is None:
            self.cache_url = self.tls_url
        return self

    @field_validator("token_expiry", mode="after")
    @classmethod
    def set_datetime_utc(cls, value: datetime) -> datetime:
        """Applies UTC timezone to datetime value."""
        # For tz-naive datetimes, treat the time as UTC in the first place
        # otherwise coerce the tz-aware datetime into UTC
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(tz=UTC)

    @field_serializer("behind_lb", "verify_host", "use_native_httplib")
    def serialize_booleans(self, value: bool) -> str:  # noqa: FBT001
        """Serialize boolean fields as string values."""
        return "on" if value else "off"


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

    # FIXME should be an enum if this sticks around
    exclusive: str | None = Field(
        description="Whether to allocate resources as `exclusive` or `exclusive-user`",
        default=None,
    )

    cores: int = Field(
        description="How many cores to reserve for resource allocation",
        default=15,
    )

    extra_arguments: str = Field(
        description="Space separated set of arbitrary extra arguments for resource allocation",
        default="",
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

    fqdn: str = Field(
        description="DNS FQDN for hosted application",
        default="https://usdf-cm-dev.slac.stanford.edu",
    )


class DaemonConfiguration(BaseModel):
    """Settings for the Daemon nested model.

    Set according to DAEMON__FIELD environment variables.
    """

    processing_interval: int = Field(
        default=30,
        description=(
            "The maximum wait time (seconds) between daemon processing intervals "
            "and the minimum time between element processing attepts. This "
            "duration may be lengthened depending on the element type."
        ),
    )


class NotificationConfiguration(BaseModel):
    """Configurations for notifications.

    Set according to NOTIFICATIONS__FIELD environment variables.
    """

    slack_webhook_url: str | None = Field(
        default=None,
        description="URL of a Slack Application webhook",
    )


class DatabaseConfiguration(BaseModel):
    """Database configuration nested model.

    Set according to DB__FIELD environment variables.
    """

    url: str = Field(
        default="",
        description="The URL for the cm-service database",
    )

    password: SecretStr | None = Field(
        default=None,
        description="The password for the cm-service database",
    )

    table_schema: str = Field(
        default="public",
        description="Schema to use for cm-service database",
    )

    echo: bool = Field(
        default=False,
        description="SQLAlchemy engine echo setting for the cm-service database",
    )

    max_overflow: int = Field(
        default=10,
        description="Maximum connection overflow allowed for QueuePool.",
    )

    pool_size: int = Field(
        default=5,
        description="Number of open connections kept in the QueuePool",
    )

    pool_recycle: int = Field(
        default=-1,
        description="Timeout in seconds before connections are recycled",
    )

    pool_timeout: int = Field(
        default=30,
        description="Wait timeout for acquiring a connection from the pool",
    )

    pool_fields: set[str] = Field(
        default={"max_overflow", "pool_size", "pool_recycle", "pool_timeout"},
        description="Set of fields used for connection pool configuration",
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
    logging: LoggingConfiguration = LOGGER_SETTINGS
    slurm: SlurmConfiguration = SlurmConfiguration()
    panda: PandaConfiguration = PandaConfiguration()
    notifications: NotificationConfiguration = NotificationConfiguration()
    features: EnabledFeatures = EnabledFeatures()

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

    aws_s3_endpoint_url: str | None = Field(
        description="An endpoint url to use with S3 APIs for the default profile",
        default=None,
        validation_alias=AliasChoices("AWS_ENDPOINT_URL_S3", "AWS_ENDPOINT_URL", "S3_ENDPOINT_URL"),
        serialization_alias="AWS_ENDPOINT_URL_S3",
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
