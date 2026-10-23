"""Model library describing the runtime data model of a Library Manifest for a
processing site or facility.
"""

from pathlib import Path
from typing import Literal

from pydantic import MISSING, Field, field_serializer

from . import SPEC_CONFIG, LibraryManifest, ManifestSpec


# FIXME determine whether to rename this to Site* or to rename facility* for
# consistency
class FacilitySpec(ManifestSpec):
    model_config = SPEC_CONFIG | {"title": "site_spec"}
    facility: Literal["SLAC", "IN2P3", "LANCS", "RAL"] = Field(
        default="SLAC",
        title="Processing Facility Name",
        description="Name of the processing facility, equivalent to the BPS `computeSite` setting",
        examples=["SLAC", "IN2P3"],
    )
    literals: dict | None = Field(
        default=None,
        title="Processing Facility Literal Configuration, used as top-level BPS configuration",
        examples=[{"site": {"SLAC": {"profile": {"condor": {"+Walltime": 43200}}}}}],
    )
    include_files: list[str] = Field(
        default_factory=list,
        title="Facility-Specific BPS Include Files",
        description="List of files to be added to the BPS submission as include files "
        "that are specific to the use of this Facility.",
        examples=[["${DRP_PIPE_DIR}/bps/caching/{instrument}/{site}/{caching}.yaml"]],
    )
    provisioned_platform: str = Field(
        default="s3df",
        title="Provisioning Platform Name",
        description="Name of the provisioning platform at the facility, for use with `allocateNodes.py`",
        examples=["s3df"],
    )
    provisioned_queue: str = Field(
        default="milano",
        title="Provisioning Queue",
        description="Name of the provisioning queue or partition for provisioned glidein",
        examples=["milano", "roma"],
    )
    provisioned_account_group: str = Field(
        default="rubin:developers",
        title="Accounting User",
        description="Name of the accounting user or group associated with the provisioned glidein",
        examples=["rubin:developers", "rubin:production"],
    )
    botocore_config_file: Path | MISSING = Field(
        default=MISSING,
        title="Botocore Config File",
        description="Path to the site-specific botocore configuration file, "
        "as an absolute path known to the launcher context.",
        examples=["/path/to/a/specific/botocore/config.ini"],
    )
    botocore_credentials_file: Path | MISSING = Field(
        default=MISSING,
        title="Botocore Credentials File",
        description="Path to the site-specific botocore shared credentials file, "
        "as an absolute path known to the launcher context.",
        examples=["/path/to/a/specific/botocore/credentials.ini"],
    )
    lsst_db_auth_file: Path | MISSING = Field(
        default=MISSING,
        title="LSST DB Authentication File",
        description="Path to the site-specific LSST database authentication file, "
        "as an absolute path known to the launcher context.",
        examples=["/path/to/a/specific/lsst/db-auth.yaml"],
    )
    lsst_data_repos_file: Path | MISSING = Field(
        default=MISSING,
        title="LSST Butler Index File",
        description="Path to the site-specific LSST butler data repo index file, "
        "as an absolute path known to the launcher context.",
        examples=["/path/to/a/specific/lsst/db-auth.yaml"],
    )
    remote_user_home: Path | MISSING = Field(
        default=MISSING,
        title="Launcher Home Directory",
        description="Path to the launcher runtime user's home directory, "
        "as an absolute path known to the launcher context.",
        examples=["/mnt/home/u/user"],
    )

    @field_serializer(
        "botocore_config_file",
        "botocore_credentials_file",
        "lsst_db_auth_file",
        "lsst_data_repos_file",
        "remote_user_home",
    )
    def as_string(self, value: Path) -> str:
        return str(value)


class FacilityManifest(LibraryManifest[FacilitySpec]): ...
