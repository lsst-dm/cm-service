"""Test parsing of provenance report JSON files/output"""

import shutil
from pathlib import Path as pyPath
from urllib.parse import urlparse
from uuid import UUID, uuid5

from anyio import Path
from httpx2 import AsyncClient

from lsst.cmservice.machines.lib import read_provenance_report_json


async def test_dirty_provenance_report() -> None:
    """Test parsing a provenance report with known issues/caveats"""

    provenance = {"prov_json": Path(__file__).parent.parent / "fixtures/bps/provenance_report_dirty.json"}
    report = await read_provenance_report_json(provenance["prov_json"])

    assert max(task.get("expected", 0) for task in report["tasks"].values()) == 116_788
    assert sum(task.get("blocked", 0) for task in report["tasks"].values()) == 3_769
    assert sum(len(task["caveats"]) for task in report["tasks"].values()) == 21
    assert sum(len(task["exceptions"]) for task in report["tasks"].values()) == 9


async def test_group_provenance_report(
    test_campaign_groups: str, aclient: AsyncClient, tmp_path: pyPath
) -> None:
    """Test the GET and POST routes for the soft and hard retrieval of a node's
    provenance report from a submit directory.
    """

    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "ash.1")

    # create a temp artifact and submit directory for the provenance report
    artifact_path = tmp_path / f"{node_id}"
    submit_path = artifact_path / "submit"
    submit_path.mkdir(parents=True)
    prov_fixture = Path(__file__).parent.parent / "fixtures/bps/provenance_report_dirty.json"
    prov_report = Path(submit_path) / f"{node_id}_prov.json"
    shutil.copy(prov_fixture, prov_report)

    # patch an artifact path to the node's metadata
    r = await aclient.patch(
        f"/v2/nodes/{node_id}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {"op": "add", "path": "/metadata/artifact_path", "value": str(artifact_path)},
            {
                "op": "add",
                "path": "/metadata/bps",
                "value": {"Run Name": f"{node_id}", "Submit dir": str(submit_path)},
            },
        ],
    )
    assert r.is_success

    new_node = r.headers["self"]
    r = await aclient.get(new_node)
    assert r.is_success

    # Soft GET doesn't have a report
    r = await aclient.get(f"{new_node}/provenance")
    assert r.is_success
    report = r.json()
    assert not report

    # Hard POST acquires the report
    r = await aclient.post(f"{new_node}/provenance")
    assert r.is_success
    report = r.json()
    assert report

    # Now the Soft GET has the report too
    r = await aclient.get(f"{new_node}/provenance")
    assert r.is_success
    report = r.json()
    assert report
