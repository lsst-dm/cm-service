import os
import re
from typing import assert_never

from pydantic import AliasChoices, BaseModel


def as_snake_case(s: str) -> str:
    """Preprocess a string by sanitizing it and producing snake case."""
    # TODO clean up unicode characters and etc
    return re.sub(r"\W+?", "_", s)


def as_templated_snake_case(s: str) -> str:
    """Preprocess a string by sanitizing it and producing snake case while
    preserving template variable placeholders.
    """
    pattern = r"(?<!\$)\{\{.*?\}\}|\W"
    return re.sub(pattern, lambda x: x.group(0) if x.group(0).startswith("{{") else "_", s)


def strip_trailing_slash(s: str) -> str:
    """Preprocess a string by stripping any trailing separator character."""
    return s.rstrip(os.sep)


def parse_env_list(value: list | dict | str) -> list | str:
    """Parses an index-mapped dictionary as a list.

    For example, the env var `FIELD__0__FOO=BAR` will be parsed as a dict like
    `FIELD={"0": {"FOO": "BAR"}}`. This validator transforms the mapping to an
    ordered list like `FIELD=[{"FOO": "BAR"}]`.
    """
    match value:
        case dict():
            return [value[k] for k in sorted(value.keys(), key=int)]
        case _:
            return value


def csv_serializer(value: str | list) -> str:
    """Serializes a list of strings to a comma-joined string."""
    match value:
        case str():
            return value
        case list():
            return ",".join(value)
        case _:
            assert_never(value)


def csv_validator(value: str | list) -> list:
    """Validates an input as a list or transforms a comma-joined string to a
    list.
    """
    match value:
        case str():
            return [v.strip() for v in value.split(",")]
        case list():
            return value
        case _:
            assert_never(value)


def model_field_names(model: type[BaseModel]) -> set[str]:
    """Returns the names of a model's fields, together with any string aliases
    by which those fields may be validated or serialized.
    """
    names = set()
    for name, field in model.model_fields.items():
        names.add(name)
        for alias in (field.alias, field.serialization_alias, field.validation_alias):
            match alias:
                case str():
                    names.add(alias)
                case AliasChoices():
                    names.update(choice for choice in alias.choices if isinstance(choice, str))
    return names
