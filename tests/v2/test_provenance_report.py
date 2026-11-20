"""Test parsing of provenance report JSON files/output"""

import shutil
from pathlib import Path as pyPath
from urllib.parse import urlparse

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
    node_name = "vasquez"
    run_name = f"{campaign_id}_{node_name}"

    # create a temp artifact and submit directory for the provenance report
    artifact_path = tmp_path / node_name
    submit_path = artifact_path / "submit"
    submit_path.mkdir(parents=True)
    prov_fixture = Path(__file__).parent.parent / "fixtures/bps/provenance_report_dirty.json"
    prov_report = Path(submit_path) / f"{run_name}_prov.json"
    shutil.copy(prov_fixture, prov_report)

    r = await aclient.post(
        "/v2/nodes",
        json={
            "apiVersion": "io.lsst.cmservice/v1",
            "kind": "node",
            "metadata": {
                "name": node_name,
                "namespace": campaign_id,
                "kind": "group",
                "artifact_path": str(artifact_path),
                "bps": {"Run Name": run_name, "Submit dir": str(submit_path)},
            },
            "spec": {},
        },
    )
    assert r.is_success

    new_node = r.headers["self"]
    r = await aclient.get(new_node)
    assert r.is_success
    assert r.json()["metadata"]["bps"]["Submit dir"] == str(submit_path)

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
