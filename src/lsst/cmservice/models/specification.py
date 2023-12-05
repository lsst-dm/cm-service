"""Pydantic models for the Specification

These tables group templates for building processing Nodes into
sets that can be used to define a Campaign
"""
from pydantic import BaseModel


class SpecificationBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Unique name for this
    name: str


class SpecificationCreate(SpecificationBase):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Specification(SpecificationBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # Primary Key
    id: int

    class Config:
        orm_mode = True


class SpecificationLoad(BaseModel):
    """Parameters need to specifiy loading a Specification file"""

    # Name of the file to load
    yaml_file: str = "examples/example_config.yaml"
