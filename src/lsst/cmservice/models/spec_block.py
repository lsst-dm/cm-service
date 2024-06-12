"""Pydantic models for the SpecBlock tables

These tables provide templates for build processing Nodes
"""
from pydantic import BaseModel, ConfigDict


class SpecBlockBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name for this
    name: str | None = None
    # Class of associated Handler
    handler: str | None = None
    # General Parameters
    data: dict | None = None
    # Parameters defining associated collection names
    collections: dict | None = None
    # Configuration of child nodes associated to this node
    child_config: dict | None = None
    # Used to override Spec Block Configuration
    spec_aliases: dict | None = None
    # Configuraiton of scripts associated to this Node
    scripts: dict | list | None = None
    # Configuraiton of scripts associated to this Node
    steps: dict | list | None = None


class SpecBlockCreate(SpecBlockBase):
    """Parameters that are used to create new rows but not in DB tables"""


class SpecBlock(SpecBlockBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int


class SpecBlockUpdate(SpecBlockBase):
    """Parameters that can be updated"""

    model_config = ConfigDict(from_attributes=True)

    # Class of associated Handler
    handler: str | None = None
    # General Parameters
    data: dict | None = None
    # Parameters defining associated collection names
    collections: dict | None = None
    # Configuration of child nodes associated to this node
    child_config: dict | None = None
    # Used to override Spec Block Configuration
    spec_aliases: dict | None = None
    # Configuraiton of scripts associated to this Node
    scripts: dict | list | None = None
    # Configuraiton of scripts associated to this Node
    steps: dict | list | None = None
