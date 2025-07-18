"""Pydantic model for the Processing Elements

These are the things that are shared between
'Campaign', 'Step', 'Group', 'Job' and 'Script'
"""

from pydantic import BaseModel, ConfigDict, Field

from ..common.enums import StatusEnum


class ElementBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Local name for this element, unique relative to parent element
    name: str

    # Parameter Overrides
    data: dict = Field(default_factory=dict)

    metadata_: dict = Field(default_factory=dict)

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

    # Fullname of the parent Node
    parent_name: str | None = None


class ElementMixin(ElementBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # primary key
    id: int

    # ForeignKey for Parent Node
    parent_id: int | None = None

    # Full unique name for this Node
    fullname: str

    # Processing Status
    status: StatusEnum = StatusEnum.waiting

    # Flag to set if this Node is superseded
    superseded: bool = False


class Element(ElementMixin):
    """Parameters that are in DB tables"""


class ElementUpdate(BaseModel):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

    # Parameter Overrides
    data: dict | None = None
    metadata_: dict | None = None

    # Overrides for configuring child nodes
    child_config: dict | str | None = None

    # Overrides for making collection names
    collections: dict | str | None = None

    # Overrides for which SpecBlocks to use in constructing child Nodes
    spec_aliases: dict | str | None = None

    # Override for Callback handler class
    handler: str | None = None

    # Processing Status
    status: StatusEnum = StatusEnum.waiting

    # Flag to set if this Node is superseded
    superseded: bool = False
