"""Pydantic model for the ScriptError tables

These tables represent errors reported from
Scripts, i.e., stuff like butler commands or
quantum graph generation failing.
"""

from pydantic import BaseModel, ConfigDict


class ScriptErrorBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # ForeignKey identifying the associated script
    script_id: int
    # Who reported This error
    source: int
    # Message associated to this error
    diagnostic_message: str


class ScriptErrorCreate(ScriptErrorBase):
    """Parameters that are used to create new rows but not in DB tables"""


class ScriptError(ScriptErrorBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # Primary Key
    id: int


class ScriptErrorUpdate(ScriptErrorBase):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

    # Who reported This error
    source: int
    # Message associated to this error
    diagnostic_message: str
