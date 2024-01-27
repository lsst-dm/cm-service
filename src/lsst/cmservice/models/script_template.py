"""Pydantic model for the ScriptTemplate tables

These represent files that provide templates
for bash scripts or pipetask configurations that
have been uploaded to the database
"""
from pydantic import BaseModel, ConfigDict


class ScriptTemplateBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this
    name: str

    # Corresponding data
    data: dict | list | None = None


class ScriptTemplateCreate(ScriptTemplateBase):
    """Parameters that are used to create new rows but not in DB tables"""


class ScriptTemplate(ScriptTemplateBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int


class ScriptTemplateUpdate(ScriptTemplateBase):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

    # Corresponding data
    data: dict | list | None = None
