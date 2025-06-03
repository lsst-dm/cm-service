import pickle
from collections.abc import Generator
from pathlib import Path

import pytest

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.handlers.functions import status_from_bps_report
from lsst.ctrl.bps.wms_service import WmsRunReport


@pytest.fixture
def pickled_bps_report(request: pytest.FixtureRequest) -> Generator[WmsRunReport]:
    """Yields a pickled bps report object from a fixture file."""
    bps_report_file = Path(__file__).parent / "fixtures" / "bps" / f"{request.param}.pickle"
    with bps_report_file.open(mode="rb") as f:
        run_reports, _ = pickle.load(f)
        yield run_reports[0]


@pytest.mark.parametrize(
    "pickled_bps_report,expected_status",
    [
        ("bps_report_fails", StatusEnum.accepted),
        ("bps_report_success", StatusEnum.accepted),
        ("bps_report_unready", StatusEnum.running),
    ],
    indirect=["pickled_bps_report"],
)
def test_parse_bps_report(pickled_bps_report: WmsRunReport, expected_status: StatusEnum) -> None:
    """Parses bps report objects and tests the status returned from them is
    consistent with expectations.

    A BPS report with failed jobs but with a successful finalJob returns a
    CM "accepted" status.
    """
    status = status_from_bps_report(pickled_bps_report)
    assert status is expected_status
