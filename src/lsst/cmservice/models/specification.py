"""Pydantic models for the Specification

These tables group templates for building processing Nodes into
sets that can be used to define a Campaign
"""
from pydantic import BaseModel, ConfigDict


class SpecificationBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Unique name for this
    name: str


class SpecificationCreate(SpecificationBase):
    """Parameters that are used to create new rows but not in DB tables"""


class Specification(SpecificationBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # Primary Key
    id: int


class SpecificationLoad(BaseModel):
    """Parameters need to specifiy loading a Specification file"""

    # Name of the file to load
    yaml_file: str = "examples/example_config.yaml"

    # Allow updating existing specifications
    allow_update: bool = False
