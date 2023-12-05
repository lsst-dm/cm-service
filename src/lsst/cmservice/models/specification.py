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

    pass


class SpecBlock(SpecBlockBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

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

    # PrimaryKey
    id: int

    # Full unique name
    fullname: str

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in SpecBlock Table
    spec_block_id: int

    class Config:
        orm_mode = True


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

    # PrimaryKey
    id: int

    # Full unique name
    fullname: str

    # Foreign Key into Specification table
    spec_id: int

    # Foreign Key in ScriptTemplate Table
    script_template_id: int

    class Config:
        orm_mode = True


class SpecificationLoad(BaseModel):
    """Parameters need to specifiy loading a Specification file"""

    # Name of the file to load
    yaml_file: str = "examples/example_config.yaml"
