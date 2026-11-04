"""Module for serialization and deserialization support for pydantic and
other derivative models.
"""

from enum import EnumType
from functools import partial
from typing import Any

from pydantic import AfterValidator, PlainSerializer, PlainValidator

from .enums import AuditActionEnum, ManifestKind, NotificationLabelEnum, StatusEnum


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
    except KeyError, ValueError:
        msg = f"Value must be a member of {enum_.__qualname__}"
        raise ValueError(msg)
    return new_enum


def check_template_expressions(value: dict[str, str]) -> dict[str, str]:
    """Validates a mapping of template variable names to expressions, i.e.,
    that each name is usable as a template variable and that each expression
    is not empty.

    Used as a Validator for a pydantic field.
    """
    for name, expression in value.items():
        if not name.isidentifier():
            msg = f"Expression name {name!r} is not a valid variable name"
            raise ValueError(msg)
        if not expression.strip():
            msg = f"Expression {name!r} is empty"
            raise ValueError(msg)
    return value


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


AuditActionEnumValidator = PlainValidator(partial(EnumValidator, enum_=AuditActionEnum))
"""A validator for the AuditActionEnum that can parse the enum from a name
or a value.
"""


NotificationLabelEnumValidator = PlainValidator(partial(EnumValidator, enum_=NotificationLabelEnum))
"""A validator for a NotificationLabelEnum that can parse the enum from a name
or a value.
"""


TemplateExpressionsValidator = AfterValidator(check_template_expressions)
"""A validator for a mapping of template variable names to expressions."""
