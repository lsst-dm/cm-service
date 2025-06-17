from typing import Annotated

from pydantic import AliasChoices
from sqlmodel import Field, SQLModel

from ..common.enums import ManifestKind
from .campaigns_v2 import EnumSerializer, ManifestKindEnumValidator


# this can probably be a BaseModel since this is not a db relation, but the
# distinction probably doesn't matter
class ManifestWrapper(SQLModel):
    """a model for an object's Manifest wrapper, used by APIs where the `spec`
    should be the kind's table model, more or less.
    """

    apiversion: str = Field(default="io.lsst.cmservice/v1")
    kind: Annotated[ManifestKind, ManifestKindEnumValidator, EnumSerializer] = Field(
        default=ManifestKind.other,
    )
    metadata_: dict = Field(
        default_factory=dict,
        schema_extra={
            "validation_alias": AliasChoices("metadata", "metadata_"),
            "serialization_alias": "metadata",
        },
    )
    spec: dict = Field(
        default_factory=dict,
        schema_extra={
            "validation_alias": AliasChoices("spec", "configuration", "data"),
            "serialization_alias": "spec",
        },
    )
