"""Tests v2 fastapi manifest routes"""

from uuid import uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_list_manifests(aclient: AsyncClient) -> None:
    x = await aclient.get("/cm-service/v2/manifests")
    assert x.is_success
    assert len(x.json()) == 0
    assert True


async def test_load_manifests(aclient: AsyncClient) -> None:
    campaign_name = uuid4().hex[-8:]

    # Try to create a campaign manifest
    x = await aclient.post(
        "/cm-service/v2/manifests",
        json={
            "apiversion": "io.lsst.cmservice/v1",
            "kind": "campaign",
            "metadata_": {},
            "spec": {},
        },
    )
    assert x.is_client_error

    # Try to create a manifest without a name
    x = await aclient.post(
        "/cm-service/v2/manifests",
        json={
            "apiversion": "io.lsst.cmservice/v1",
            "kind": "other",
            "metadata_": {},
            "spec": {},
        },
    )
    assert x.is_client_error

    # Try to create a manifest with an unknown namespace
    x = await aclient.post(
        "/cm-service/v2/manifests",
        json={
            "apiversion": "io.lsst.cmservice/v1",
            "kind": "other",
            "metadata_": {
                "name": uuid4().hex[-8:],
                "namespace": campaign_name,
            },
            "spec": {},
        },
    )
    assert x.is_client_error

    # Create a manifest in the default namespace
    x = await aclient.post(
        "/cm-service/v2/manifests",
        json={
            "apiversion": "io.lsst.cmservice/v1",
            "kind": "other",
            "metadata_": {
                "name": uuid4().hex[-8:],
            },
            "spec": {
                "one": 1,
                "two": 2,
                "three": 4,
            },
        },
    )
    assert x.is_success

    # Create a campaign for additional manifests
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "kind": "campaign",
            "metadata": {"name": campaign_name},
            "spec": {},
        },
    )
    assert x.is_success
    campaign_id = x.json()["id"]

    # Create multiple manifests in the campaign namespace by both its name and
    # its id. The first uses the most "proper" manifest field names "metadata"
    # and "spec"; the second uses alternate "metadata_" and "data" aliases.
    x = await aclient.post(
        "/cm-service/v2/manifests",
        json=[
            {
                "apiversion": "io.lsst.cmservice/v1",
                "kind": "other",
                "metadata": {
                    "name": uuid4().hex[-8:],
                    "namespace": campaign_id,
                },
                "spec": {
                    "one": 1,
                    "two": 2,
                    "three": 4,
                },
            },
            {
                "apiversion": "io.lsst.cmservice/v1",
                "kind": "other",
                "metadata_": {
                    "name": uuid4().hex[-8:],
                    "namespace": campaign_name,
                },
                "data": {
                    "one": 1,
                    "two": 2,
                    "three": 4,
                },
            },
        ],
    )
    assert x.is_success

    # Get all the loaded manifests
    x = await aclient.get("/cm-service/v2/manifests")
    assert x.is_success
    manifests = x.json()
    assert len(manifests) == 3
    assert manifests[-1]["spec"]["one"] == 1


async def test_patch_manifest(aclient: AsyncClient) -> None:
    """Tests partial update of manifests and single resource retrieval."""
    campaign_name = uuid4().hex[-8:]
    manifest_name = uuid4().hex[-8:]

    # Create a campaign and a manifest
    x = await aclient.post(
        "/cm-service/v2/campaigns",
        json={
            "kind": "campaign",
            "metadata": {"name": campaign_name},
            "spec": {},
        },
    )
    assert x.is_success

    x = await aclient.post(
        "/cm-service/v2/manifests",
        json={
            "apiversion": "io.lsst.cmservice/v1",
            "kind": "other",
            "metadata": {
                "name": manifest_name,
                "namespace": campaign_name,
            },
            "spec": {
                "one": 1,
                "two": 2,
                "three": 4,
                "a_list": ["a", "b", "c", "e"],
            },
        },
    )

    # "Correct" the spec of the loaded manifest
    x = await aclient.patch(
        f"/cm-service/v2/manifests/{manifest_name}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {
                "op": "replace",
                "path": "/spec/three",
                "value": 3,
            },
            {
                "op": "replace",
                "path": "/spec/a_list/3",
                "value": "d",
            },
            {
                "op": "add",
                "path": "/spec/four",
                "value": 4,
            },
            {
                "op": "add",
                "path": "/spec/owner",
                "value": "bob_loblaw",
            },
        ],
    )
    assert x.is_success
    patched_manifest = x.json()
    assert patched_manifest["version"] == 2
    assert patched_manifest["spec"]["three"] == 3
    assert patched_manifest["spec"]["a_list"][3] == "d"
    assert patched_manifest["spec"]["four"] == 4
    assert patched_manifest["spec"]["owner"] == "bob_loblaw"

    # In the previous test we added the "owner" to the wrong path, so now we
    # want to <move> it from spec->metadata
    x = await aclient.patch(
        f"/cm-service/v2/manifests/{manifest_name}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {
                "op": "move",
                "path": "/metadata/owner",
                "from": "/spec/owner",
            }
        ],
    )
    assert x.is_success
    patched_manifest = x.json()
    assert patched_manifest["version"] == 3
    assert patched_manifest["metadata"]["owner"] == "bob_loblaw"
    assert "owner" not in patched_manifest["spec"]

    # Using the "test" operator as a gating function, try but fail to update
    # the previously moved owner field
    x = await aclient.patch(
        f"/cm-service/v2/manifests/{manifest_name}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {
                "op": "test",
                "path": "/spec/owner",
                "value": "bob_loblaw",
            },
            {
                "op": "replace",
                "path": "/spec/owner",
                "value": "lob_boblaw",
            },
            {
                "op": "add",
                "path": "/metadata/scope",
                "value": "drp",
            },
        ],
    )
    assert x.is_client_error

    # Get the manifest with multiple versions
    # First, make sure when not indicated, the most recent version is returned
    # Note: the previous patch with a failing test op must not have created any
    # new version.
    x = await aclient.get(f"/cm-service/v2/manifests/{manifest_name}")
    assert x.is_success
    assert x.json()["version"] == 3

    # RFC6902 prescribes an all-or-nothing patch operation, so the previous op
    # with a failing test assertion must not have otherwise completed, e.g.,
    # the addition of a "scope" key to the manifest's metadata
    assert "scope" not in x.json().get("metadata")

    # Next, get a specific version of the manifest
    x = await aclient.get(f"/cm-service/v2/manifests/{manifest_name}?version=2")
    assert x.is_success
    assert x.json()["version"] == 2
