"""Pydantic models for the SpecBlockAssociation tables

These tables connect individual SpecBlocks into Specifications
that can be used to build entire campaigns
"""
from pydantic import BaseModel, ConfigDict


class SpecBlockAssociationBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this
    alias: str


class SpecBlockAssociationCreate(SpecBlockAssociationBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the Specification
    spec_name: str

    # Name of the SpecBlock
    spec_block_name: str


class SpecBlockAssociation(SpecBlockAssociationBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int

    # Full unique name
    fullname: str

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in SpecBlock Table
    spec_block_id: int


class SpecBlockAssociationUpdate(SpecBlockAssociationBase):
    """Parameters that can be updated"""

    model_config = ConfigDict(from_attributes=True)

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in SpecBlock Table
    spec_block_id: int
