"""Pydantic model for the Processing Elements

These are the things that are shared between
'Campaign', 'Step', 'Group', 'Job' and 'Script'
"""

from pydantic import BaseModel

from ..common.enums import StatusEnum


class ElementBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Local name for this element, unique relative to parent element
    name: str

    # Parameter Overrides
    data: dict | str | None = None

    # Overrides for configuring child nodes
    child_config: dict | str | None = None

    # Overrides for making collection names
    collections: dict | str | None = None

    # Overrides for which SpecBlocks to use in constructing child Nodes
    spec_aliases: dict | str | None = None

    # Override for Callback handler class
    handler: str | None = None


class ElementCreateMixin(ElementBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Name of the SpecBlockAssociation
    spec_block_assoc_name: str | None = None

    # Name of the Specification to use as a template
    spec_name: str | None = None

    # Name of the SpecBlock to use as a template
    spec_block_name: str | None = None

    # Fullname of the parent Node
    parent_name: str


class ElementMixin(ElementBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # primary key
    id: int

    # ForeignKey for SpecBlockAssociation
    spec_block_assoc_id: int

    # ForeignKey for Parent Node
    parent_id: int

    # Full unique name for this Node
    fullname: str

    # Processing Status
    status: StatusEnum = StatusEnum.waiting

    # Flag to set if this Node is superseded
    superseded: bool = False

    class Config:
        orm_mode = True


class Element(ElementMixin):
    pass
