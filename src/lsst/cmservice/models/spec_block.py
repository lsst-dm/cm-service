"""Pydantic models for the SpecBlock tables

These tables provide templates for build processing Nodes
"""
from pydantic import BaseModel


class SpecBlockBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this
    name: str
    # Class of associated Handler
    handler: str | None = None
    # General Parameters
    data: dict | list | None
    # Parameters defining associated collection names
    collections: dict | list | None
    # Configuration of child nodes associated to this node
    child_config: dict | list | None
    # Used to override Spec Block Configuration
    spec_aliases: dict | list | None
    # Configuraiton of scripts associated to this Node
    scripts: dict | list | None


class SpecBlockCreate(SpecBlockBase):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class SpecBlock(SpecBlockBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

    class Config:
        orm_mode = True
