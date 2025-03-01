from pydantic import BaseModel

from ..common.enums import StatusEnum


class RematchQuery(BaseModel):
    """Parameters needed to run error matching"""

    # Rematch error that are already matched
    rematch: bool = False


class ResetQuery(BaseModel):
    """Parameters needed to call reset functions"""

    # fake reset
    fake_reset: bool = False

    # Status to set
    status: StatusEnum = StatusEnum.waiting


class FullnameQuery(BaseModel):
    """Parameters needed to run query by fullname"""

    # Fullname of Node
    fullname: str | None = None


class NameQuery(BaseModel):
    """Parameters needed to run query by name"""

    # Name of Node
    name: str | None = None


class NodeQuery(BaseModel):
    """Parameters needed to run query for Node"""

    fullname: str | None = None


class UpdateNodeQuery(NodeQuery):
    """Parameters needed to update a Node"""

    # Value to update
    update_dict: dict


class ProcessQuery(FullnameQuery):
    """Parameters needed to process a Node"""

    # If set, set the status without actually processing
    fake_status: StatusEnum | None = None


class ProcessNodeQuery(NodeQuery):
    """Parameters needed to process a Node"""

    # If set, set the status without actually processing
    fake_status: int | None = None


class UpdateStatusQuery(NodeQuery):
    """Parameters needed to update the status of a Node"""

    # Status to set
    status: StatusEnum


class ScriptQueryBase(FullnameQuery):
    """Parameters needed to run query for Scripts associted to a Node"""

    # Name of the script
    script_name: str | None = None


class RetryScriptQuery(ScriptQueryBase):
    """Parameters needed to retry a script associated to a Node"""

    # fake reset
    fake_reset: bool = False

    # Status to set
    status: StatusEnum = StatusEnum.waiting


class ResetScriptQuery(FullnameQuery):
    """Parameters needed to call reset functions"""

    # fake reset
    fake_reset: bool = False

    # Status to set
    status: StatusEnum = StatusEnum.waiting


class ScriptQuery(ScriptQueryBase):
    """Parameters needed to run query for Scripts associated to a Node"""

    # If True, return only unprocessed Scripts
    remaining_only: bool = False
    # If True, skip all scripts marked as Superseded
    skip_superseded: bool = True


class JobQuery(FullnameQuery):
    """Parameters needed to identify a Job"""

    # If True, return only unprocessed Jobs
    remaining_only: bool = False
    # If True, skip all Jobs marked as Superseded
    skip_superseded: bool = True


class AddSteps(FullnameQuery):
    """Parameters needed to add steps to an existing campaign"""

    # Configurations for new steps
    child_configs: list


class YamlFileQuery(BaseModel):
    """Parameters needed to load a yaml file"""

    # Filename
    yaml_file: str


class LoadAndCreateCampaign(YamlFileQuery):
    """Parameters needed to load an create campaigns"""

    # Name of the campaign
    name: str
    # Name of the associated production
    parent_name: str
    # Combined name of Specification and SpecBlock
    # If empty use {spec_name}#campaign
    spec_block_assoc_name: str | None = None
    # Parameter Overrides
    data: dict | str | None = None
    # Overrides for configuring child nodes
    child_config: dict | str | None = None
    # Overrides for making collection names
    collections: dict | str | None = None
    # Overrides for which SpecBlocks to use in constructing child Nodes
    spec_aliases: dict | str | None = None
    # Override for Callback handler class
    handler: str | None = None
    # Allow updating existing specifications
    allow_update: bool = False


class LoadManifestReport(YamlFileQuery, FullnameQuery):
    """Parameters needed to load a report produced by pipetask report"""
