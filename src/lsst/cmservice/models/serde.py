"""Module for serialization and deserialization support for pydantic and
other derivative models.
"""

from enum import EnumType
from functools import partial
from typing import Any

from pydantic import PlainSerializer, PlainValidator

from ..common.enums import ManifestKind, StatusEnum


def EnumValidator[T: EnumType](value: Any, enum_: T) -> T:
    """Create an enum from the input value. The input can be either the
    enum name or its value.

    Used as a Validator for a pydantic field.
    """
    try:
        if isinstance(value, str):
            # if enum name lookup doesn't work, try its upper-case version
            value = value if value in enum_.__members__ else value.upper()
        new_enum: T = enum_[value] if value in enum_.__members__ else enum_(value)
    except (KeyError, ValueError):
        msg = f"Value must be a member of {enum_.__qualname__}"
        raise ValueError(msg)
    return new_enum


EnumSerializer = PlainSerializer(
    lambda x: x.name.lower(),
    return_type="str",
    when_used="always",
)
"""A serializer for enums that produces its name, not the value."""


StatusEnumValidator = PlainValidator(partial(EnumValidator, enum_=StatusEnum))
"""A validator for the StatusEnum that can parse the enum from either a name
or a value.
"""


ManifestKindEnumValidator = PlainValidator(partial(EnumValidator, enum_=ManifestKind))
"""A validator for the ManifestKindEnum that can parse the enum from a name
or a value.
"""
