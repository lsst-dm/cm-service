from pydantic import BaseModel

from ..common.enums import LevelEnum, ScriptMethod, StatusEnum


class ScriptBase(BaseModel):
    name: str
    attempt: int = 0
    method: ScriptMethod = ScriptMethod.slurm
    parent_level: LevelEnum
    handler: str | None = None
    data: dict | None = None
    child_config: dict | None = None
    collections: dict | None = None
    script_url: str | None = None
    stamp_url: str | None = None
    log_url: str | None = None


class ScriptCreate(ScriptBase):
    spec_block_name: str
    parent_name: str


class Script(ScriptBase):
    id: int
    spec_block_id: int
    parent_id: int
    c_id: int | None = None
    s_id: int | None = None
    g_id: int | None = None
    fullname: str
    status: StatusEnum = StatusEnum.waiting
    superseded: bool = False

    class Config:
        orm_mode = True
