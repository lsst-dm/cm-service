"""Test parsing of provenance report JSON files/output"""

from anyio import Path

from lsst.cmservice.machines.lib import read_provenance_report_json


async def test_dirty_provenance_report() -> None:
    """Test parsing a provenance report with known issues/caveats"""
    provenance = {"prov_json": Path(__file__).parent.parent / "fixtures/bps/provenance_report_dirty.json"}
    report = await read_provenance_report_json(provenance["prov_json"])

    assert max(task.get("expected", 0) for task in report["tasks"].values()) == 116_788
    assert sum(task.get("blocked", 0) for task in report["tasks"].values()) == 3_769
    assert sum(len(task["caveats"]) for task in report["tasks"].values()) == 21
    assert sum(len(task["exceptions"]) for task in report["tasks"].values()) == 9
