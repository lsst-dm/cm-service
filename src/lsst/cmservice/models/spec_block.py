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
    data: dict | None
    # Parameters defining associated collection names
    collections: dict | None
    # Configuration of child nodes associated to this node
    child_config: dict | None
    # Used to override Spec Block Configuration
    spec_aliases: dict | None
    # Configuraiton of scripts associated to this Node
    scripts: dict | list | None
    # Configuraiton of scripts associated to this Node
    steps: dict | list | None


class SpecBlockCreate(SpecBlockBase):
    """Parameters that are used to create new rows but not in DB tables"""


class SpecBlock(SpecBlockBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

    class Config:
        orm_mode = True
