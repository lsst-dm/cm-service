"""Pydantic models for the Specification and SpecBlock tables

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

    # Name of associated Specification
    spec_name: str


class SpecBlock(SpecBlockBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

    # ForeignKey giving the associated Specification
    spec_id: int

    # Unique name for this specification
    fullname: str

    class Config:
        orm_mode = True


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

    # Name of the Specficiation to create
    spec_name: str = "example"

    # Name of the file to load
    yaml_file: str = "examples/example_config.yaml"
