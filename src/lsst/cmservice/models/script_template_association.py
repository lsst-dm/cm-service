"""Pydantic models for the ScriptTemplateAssociation tables

These tables connect individual ScriptTemplates to Specifications that
can be used to build entire Campaigns
"""
from pydantic import BaseModel, ConfigDict


class ScriptTemplateAssociationBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this
    alias: str


class ScriptTemplateAssociationCreate(ScriptTemplateAssociationBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the Specification
    spec_name: str

    # Name of the ScriptTemplate
    script_template_name: str


class ScriptTemplateAssociation(ScriptTemplateAssociationBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int

    # Full unique name
    fullname: str

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in ScriptTemplate Table
    script_template_id: int


class ScriptTemplateAssociationUpdate(ScriptTemplateAssociationBase):
    """Parameters that can be updated"""

    model_config = ConfigDict(from_attributes=True)

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in ScriptTemplate Table
    script_template_id: int
