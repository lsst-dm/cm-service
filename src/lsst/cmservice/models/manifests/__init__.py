from copy import deepcopy
from typing import Any, cast

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, create_model
from pydantic.alias_generators import to_snake

from ...common.enums import ManifestKind
from ...common.types import KindField
from ...db.manifests_v2 import ManifestSpec as ManifestSpec
from ...db.manifests_v2 import VersionedMetadata


class LibraryManifest[SpecT](BaseModel):
    """A parameterized model for a Library Manifest, used to build a config-
    uration document for a particular kind of spec.
    """

    kind: KindField = Field(default=ManifestKind.other)
    metadata_: VersionedMetadata = Field(
        validation_alias=AliasChoices("metadata", "metadata_"),
        serialization_alias="metadata",
    )
    spec: SpecT = Field(
        validation_alias=AliasChoices("spec", "configuration", "data"),
        serialization_alias="spec",
    )


def model_title_generator(cls: type[BaseModel]) -> str:
    """Given a pydantic Model, returns the name of the model in snake_case."""
    return to_snake(cls.__name__)


class SubfieldManifest[T: BaseModel]:
    """Create a variant of a Pydantic Model with all fields optional.

    This class allows the use of a more restrictive model as a subfield in
    another model such that all fields in the submodel are "optional" in that
    they do not need to be supplied, but if they are they remain subject to
    any type restrictions.

    Parameters
    ----------
    T : type[BaseModel]
        The pydantic BaseModel type to enable for Subfield use.

    Returns
    -------
    type[T]
        A new model class with the same config and fields as the input model,
        but all fields are made optional (i.e., may be missing but not None).

    Notes
    -----
    - The original model's configuration is preserved.
    - Nested submodels are handled correctly.
    - Fields remain strongly typed - if present, they must match the original
      type.
    """

    def __class_getitem__(cls, model: type[T]) -> type[T]:
        fields: dict[str, Any] = {}

        for field_name, field_info in model.model_fields.items():
            new_field_info = deepcopy(field_info)
            new_field_info.default = None
            new_field_info.default_factory = None
            fields[field_name] = (field_info.annotation, new_field_info)

        subfield_model = create_model(f"{model.__name__}SubField", __config__=model.model_config, **fields)
        subfield_model.model_rebuild()
        return cast(type[T], subfield_model)


SPEC_CONFIG = ConfigDict(
    model_title_generator=model_title_generator,
    extra="forbid",
    str_strip_whitespace=True,
)
"""A common pydantic model configuration for use with multiple models."""
