from pydantic import BaseModel

from ..common.enums import StatusEnum


class RematchQuery(BaseModel):
    rematch: bool = False


class FullnameQuery(BaseModel):
    fullname: str


class NodeQuery(FullnameQuery):
    pass


class UpdateNodeQuery(NodeQuery):
    update_dict: dict


class ProcessQuery(FullnameQuery):
    fake_status: int | None = None


class ProcessNodeQuery(NodeQuery):
    fake_status: int | None = None


class UpdateStatusQuery(NodeQuery):
    status: StatusEnum


class ScriptQueryBase(FullnameQuery):
    script_name: str


class ScriptQuery(ScriptQueryBase):
    remaining_only: bool = False
    skip_superseded: bool = True


class JobQuery(FullnameQuery):
    remaining_only: bool = False
    skip_superseded: bool = True


class AddGroups(FullnameQuery):
    child_configs: dict


class AddSteps(FullnameQuery):
    child_configs: dict


class YamlFileQuery(BaseModel):
    yaml_file: str


class LoadAndCreateCampaign(YamlFileQuery):
    name: str
    parent_name: str
    spec_name: str | None = None
    spec_block_name: str | None = None
    data: dict | str | None = None
    child_config: dict | str | None = None
    collections: dict | str | None = None
    spec_aliases: dict | str | None = None
    handler: str | None = None


class LoadManifestReport(YamlFileQuery, FullnameQuery):
    pass
