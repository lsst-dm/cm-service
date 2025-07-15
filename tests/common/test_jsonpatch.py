from typing import Any

import pytest

from lsst.cmservice.common.jsonpatch import JSONPatch, JSONPatchError, apply_json_merge, apply_json_patch


@pytest.fixture
def target_object() -> dict[str, Any]:
    return {
        "apiVersion": "io.lsst.cmservice/v1",
        "spec": {
            "one": 1,
            "two": 2,
            "three": 4,
            "a_list": ["a", "b", "c", "e"],
            "tag_list": ["yes", "yeah", "yep"],
        },
        "metadata": {
            "owner": "bob_loblaw",
        },
    }


def test_jsonpatch_add(target_object: dict[str, Any]) -> None:
    """Tests the use of an add operation with a JSON Patch."""

    # Fail to add a value to an element that does not exist
    op = JSONPatch(op="add", path="/spec/b_list/0", value="a")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # Fix the missing "four" property in the spec
    op = JSONPatch(op="add", path="/spec/four", value=4)
    target_object = apply_json_patch(op, target_object)
    assert target_object["spec"].get("four") == 4

    # Insert the missing "d" value in the spec's a_list property
    op = JSONPatch(op="add", path="/spec/a_list/3", value="d")
    target_object = apply_json_patch(op, target_object)
    assert target_object["spec"].get("a_list")[3] == "d"
    assert target_object["spec"].get("a_list")[4] == "e"

    # Append to an existing list using "-"
    op = JSONPatch(op="add", path="/spec/a_list/-", value="f")
    target_object = apply_json_patch(op, target_object)
    assert len(target_object["spec"]["a_list"]) == 6
    assert target_object["spec"]["a_list"][-1] == "f"


def test_jsonpatch_replace(target_object: dict[str, Any]) -> None:
    """Tests the use of a replace operation with a JSON Patch."""

    # Fail to replace a value for a missing key
    op = JSONPatch(op="replace", path="/spec/five", value=5)
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # Fail to replace a value for a missing index
    op = JSONPatch(op="replace", path="/spec/a_list/4", value="e")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # Fix the incorrect "three" property in the spec
    op = JSONPatch(op="replace", path="/spec/three", value=3)
    target_object = apply_json_patch(op, target_object)
    assert target_object["spec"]["three"] == 3


def test_jsonpatch_remove(target_object: dict[str, Any]) -> None:
    """Tests the use of a remove operation with a JSON Patch."""

    # Remove the first element ("a") of the "a_list" property in the spec
    op = JSONPatch(op="remove", path="/spec/a_list/0")
    target_object = apply_json_patch(op, target_object)
    assert target_object["spec"]["a_list"][0] == "b"

    # Remove the a non-existent index from the same list (not an error)
    op = JSONPatch(op="remove", path="/spec/a_list/8")
    target_object = apply_json_patch(op, target_object)
    assert len(target_object["spec"]["a_list"]) == 3

    # Remove the previously added key "four" element in the spec
    op = JSONPatch(op="remove", path="/spec/four")
    target_object = apply_json_patch(op, target_object)
    assert "four" not in target_object["spec"].keys()

    # Repeat the previous removal (not an error)
    op = JSONPatch(op="remove", path="/spec/four")
    target_object = apply_json_patch(op, target_object)


def test_jsonpatch_move(target_object: dict[str, Any]) -> None:
    """Tests the use of a move operation with a JSON Patch."""

    # move the tags list from spec to metadata
    op = JSONPatch(op="move", path="/metadata/tag_list", from_="/spec/tag_list")
    target_object = apply_json_patch(op, target_object)
    assert "tag_list" not in target_object["spec"].keys()
    assert "tag_list" in target_object["metadata"].keys()

    # Fail to move a nonexistent object
    op = JSONPatch(op="move", path="/spec/yes_such_list", from_="/spec/no_such_list")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)


def test_jsonpatch_copy(target_object: dict[str, Any]) -> None:
    """Tests the use of a copy operation with a JSON Patch."""

    # copy the owner from metadata to spec as the name "pilot"
    op = JSONPatch(op="copy", path="/spec/pilot", from_="/metadata/owner")
    target_object = apply_json_patch(op, target_object)
    assert target_object["spec"]["pilot"] == target_object["metadata"]["owner"]

    # Fail to copy a nonexistent object
    op = JSONPatch(op="copy", path="/spec/yes_such_list", from_="/spec/no_such_list")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)


def test_jsonpatch_test(target_object: dict[str, Any]) -> None:
    """Tests the use of a test/assert operation with a JSON Patch."""

    # test successful assertion
    op = JSONPatch(op="test", path="/metadata/owner", value="bob_loblaw")
    _ = apply_json_patch(op, target_object)

    op = JSONPatch(op="test", path="/spec/a_list/0", value="a")
    _ = apply_json_patch(op, target_object)

    # test value mismatch
    op = JSONPatch(op="test", path="/metadata/owner", value="bob_alice")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # test missing key
    op = JSONPatch(op="test", path="/metadata/pilot", value="bob_alice")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # test missing index
    op = JSONPatch(op="test", path="/spec/a_list/8", value="bob_alice")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)

    # test bad reference token
    op = JSONPatch(op="test", path="/spec/a_list/-", value="bob_alice")
    with pytest.raises(JSONPatchError):
        _ = apply_json_patch(op, target_object)


def test_json_merge_patch(target_object: dict[str, Any]) -> None:
    """Tests the RFC7396 JSON Merge patch function."""

    patch = {
        "metadata": {"owner": None, "pilot": "bob_loblaw"},
        "spec": {"new_key": {"new_key": "new_value"}},
    }
    new_object = apply_json_merge(patch, target_object)

    assert new_object["metadata"]["pilot"] == "bob_loblaw"
    assert "owner" not in new_object["metadata"]
    assert new_object["spec"]["new_key"]["new_key"] == "new_value"
