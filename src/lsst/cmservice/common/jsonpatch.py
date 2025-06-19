"""Module implementing functions to support json-patch operations on Python
objects based on RFC6902.
"""

import operator
from collections.abc import MutableMapping, MutableSequence
from functools import reduce
from typing import TYPE_CHECKING, Any, Literal

from pydantic import AliasChoices, BaseModel, Field

type AnyMutable = MutableMapping | MutableSequence


class JSONPatchError(Exception):
    """Exception raised when a JSON patch operation cannot be completed."""

    pass


class JSONPatch(BaseModel):
    """Model representing a PATCH operation using RFC6902.

    This model will generally be accepted as a ``Sequence[JSONPatch]``.
    """

    op: Literal["add", "remove", "replace", "move", "copy", "test"]
    path: str = Field(
        description="An RFC6901 JSON Pointer", pattern=r"^\/(metadata|spec|configuration|metadata_|data)\/.*$"
    )
    value: Any | None = None
    from_: str | None = Field(
        default=None,
        pattern=r"^\/(metadata|spec|configuration|metadata_|data)\/.*$",
        validation_alias=AliasChoices("from", "from_"),
    )


def apply_json_patch[T: MutableMapping](op: JSONPatch, o: T) -> T:
    """Applies a jsonpatch to an object, returning the modified object.

    Modifications are made in-place (i.e., the input object is not copied).

    Notes
    -----
    While this JSON Patch operation nominally implements RFC6902, there are
    some edge cases inappropriate to the application that are supported by the
    RFC but disallowed through lack of support:

    - Unsupported: JSON pointer values that refer to object/dict keys that are
      numeric, e.g., {"1": "first", "2": "second"}
    - Unsupported: JSON pointer values that refer to an entire object, e.g.,
      "" -- the JSON Patch must have a root element ("/") per the model.
    - Unsupported: JSON pointer values taht refer to a nameless object, e.g.,
      "/" -- JSON allows object keys to be the empty string ("") but this is
      disallowed by the application.
    """
    # The JSON Pointer root value is discarded as the rest of the pointer is
    # split into parts
    op_path = op.path.split("/")[1:]

    # The terminal path part is either the name of a key or an index in a list
    # FIXME this assumes that an "integer-string" in the path is always refers
    #       to a list index, although it could just as well be a key in a dict
    #       like ``{"1": "first, "2": "second"}`` which is complicated by the
    #       fact that Python dict keys can be either ints or strs but this is
    #       not allowed in JSON (i.e., object keys MUST be strings)
    # FIXME this doesn't support, e.g., nested lists with multiple index values
    #       in the path, e.g., ``[["a", "A"], ["b", "B"]]``
    target_key_or_index: str | None = op_path.pop()
    if target_key_or_index is None:
        raise JSONPatchError("JSON Patch operations on empty keys not allowed.")

    reference_token: int | str
    # the reference token is referring to a an array index if the token is
    # numeric or is the single character "-"
    if target_key_or_index == "-":
        reference_token = target_key_or_index
    elif target_key_or_index.isnumeric():
        reference_token = int(target_key_or_index)
    else:
        reference_token = str(target_key_or_index)

    # The remaining parts of the path are a pointer to the object needing
    # modification, which should reduce to either a dict or a list
    try:
        op_target: AnyMutable = reduce(operator.getitem, op_path, o)
    except KeyError:
        raise JSONPatchError(f"Path {op.path} not found in object")

    match op:
        case JSONPatch(op="add", value=new_value):
            if reference_token == "-" and isinstance(op_target, MutableSequence):
                # The "-" reference token is unique to the add operation and
                # means the next element beyond the end of the current list
                op_target.append(new_value)
            elif isinstance(reference_token, int) and isinstance(op_target, MutableSequence):
                op_target.insert(reference_token, new_value)
            elif isinstance(reference_token, str) and isinstance(op_target, MutableMapping):
                op_target[reference_token] = new_value

        case JSONPatch(op="replace", value=new_value):
            # The main difference between replace and add is that replace will
            # not create new properties or elements in the target
            if reference_token == "-":
                raise JSONPatchError("Cannot use reference token `-` with replace operation.")
            elif isinstance(op_target, MutableMapping):
                try:
                    assert reference_token in op_target.keys()
                except AssertionError:
                    raise JSONPatchError(f"Cannot replace missing key {reference_token} in object")
            elif isinstance(reference_token, int) and isinstance(op_target, MutableSequence):
                try:
                    assert reference_token < len(op_target)
                except AssertionError:
                    raise JSONPatchError(f"Cannot replace missing index {reference_token} in object")

            if TYPE_CHECKING:
                assert isinstance(op_target, MutableMapping)
            op_target[reference_token] = new_value

        case JSONPatch(op="remove"):
            if isinstance(reference_token, str) and isinstance(op_target, MutableMapping):
                if reference_token == "-":
                    raise JSONPatchError("Removal operations not allowed on `-` reference token")
                _ = op_target.pop(reference_token, None)
            elif isinstance(reference_token, int):
                try:
                    _ = op_target.pop(reference_token)
                except IndexError:
                    # The index we are meant to remove does not exist, but that
                    # is not an error (idempotence)
                    pass
            else:
                # This should be unreachable
                raise ValueError("Reference token in JSON Patch must be int | str")

        case JSONPatch(op="move", from_=from_location):
            # the move operation is equivalent to a remove(from) + add(target)
            if TYPE_CHECKING:
                assert from_location is not None

            # Handle the from_location with the same logic as the op.path
            from_path = from_location.split("/")[1:]

            # Is the last element of the from_path an index or a key?
            from_target: str | int = from_path.pop()
            try:
                from_target = int(from_target)
            except ValueError:
                pass

            try:
                from_object = reduce(operator.getitem, from_path, o)
                value = from_object[from_target]
            except (KeyError, IndexError):
                raise JSONPatchError(f"Path {from_location} not found in object")

            # add the value to the new location
            op_target[reference_token] = value  # type: ignore[index]
            # and remove it from the old
            _ = from_object.pop(from_target)

        case JSONPatch(op="copy", from_=from_location):
            # The copy op is the same as the move op except the original is not
            # removed
            if TYPE_CHECKING:
                assert from_location is not None

            # Handle the from_location with the same logic as the op.path
            from_path = from_location.split("/")[1:]

            # Is the last element of the from_path an index or a key?
            from_target = from_path.pop()
            try:
                from_target = int(from_target)
            except ValueError:
                pass

            try:
                from_object = reduce(operator.getitem, from_path, o)
                value = from_object[from_target]
            except (KeyError, IndexError):
                raise JSONPatchError(f"Path {from_location} not found in object")

            # add the value to the new location
            op_target[reference_token] = value  # type: ignore[index]

        case JSONPatch(op="test", value=assert_value):
            # assert that the patch value is present at the patch path
            # The main difference between test and replace is that test does
            # not make any modifications after its assertions
            if reference_token == "-":
                raise JSONPatchError("Cannot use reference token `-` with test operation.")
            elif isinstance(op_target, MutableMapping):
                try:
                    assert reference_token in op_target.keys()
                except AssertionError:
                    raise JSONPatchError(
                        f"Test operation assertion failed: Key {reference_token} does not exist at {op.path}"
                    )
            elif isinstance(reference_token, int) and isinstance(op_target, MutableSequence):
                try:
                    assert reference_token < len(op_target)
                except AssertionError:
                    raise JSONPatchError(
                        f"Test operation assertion failed: "
                        f"Index {reference_token} does not exist at {op.path}"
                    )

            if TYPE_CHECKING:
                assert isinstance(op_target, MutableMapping)
            try:
                assert op_target[reference_token] == assert_value
            except AssertionError:
                raise JSONPatchError(
                    f"Test operation assertion failed: {op.path} does not match value {assert_value}"
                )

        case _:
            # Model validation should prevent this from ever happening
            raise JSONPatchError(f"Unknown JSON Patch operation: {op.op}")

    return o
