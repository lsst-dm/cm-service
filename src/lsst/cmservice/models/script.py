from pydantic import BaseModel

from ..common.enums import LevelEnum, ScriptMethodEnum, StatusEnum


class ScriptBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this script
    name: str
    # Attempt number from this script
    attempt: int = 0
    # Method used to process this script
    method: ScriptMethodEnum = ScriptMethodEnum.slurm
    # Override for Callback handler class
    handler: str | None = None
    # Parameter Overrides
    data: dict | None = None
    # Overrides for configuring child nodes
    child_config: dict | None = None
    # Overrides for making collection names
    collections: dict | None = None
    # URL for script file
    script_url: str | None = None
    # URL used to check script processing
    stamp_url: str | None = None
    # URL for processing log file
    log_url: str | None = None


class ScriptCreate(ScriptBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of associated SpecBlock
    spec_block_name: str
    # Name of Parent Node
    parent_name: str


class Script(ScriptBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # Primary Key
    id: int

    # ForeignKey giving associated SpecBlock
    spec_block_id: int
    # Id of parent Node
    parent_id: int
    # Level of parent Node
    parent_level: LevelEnum

    # ForeignKey giving associated Campaign
    c_id: int | None = None
    # ForeignKey giving associated Step
    s_id: int | None = None
    # ForeignKey giving associated Gropu
    g_id: int | None = None
    # Unique name for this script
    fullname: str
    # Status of processing
    status: StatusEnum = StatusEnum.waiting
    # True is Script is superseded
    superseded: bool = False

    class Config:
        orm_mode = True
