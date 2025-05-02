import pickle
from collections.abc import Generator
from pathlib import Path

import pytest

from lsst.cmservice.common.enums import StatusEnum
from lsst.cmservice.handlers.functions import status_from_bps_report
from lsst.ctrl.bps.wms_service import WmsRunReport


@pytest.fixture
def bps_report_with_failures() -> Generator[WmsRunReport]:
    """Yields a bps report object from a fixture file."""
    bps_report_file = Path(__file__).parent / "fixtures" / "bps" / "bps_report_fails.pickle"
    with open(bps_report_file, "rb") as f:
        run_reports, _ = pickle.load(f)
        yield run_reports[0]


def test_parse_bps_report_with_failures(bps_report_with_failures: WmsRunReport) -> None:
    """Parses bps report objects and tests the status returned from them is
    consistent with expectations.
    """
    # A BPS report with failed jobs but with a successful finalJob returns a
    # CM "accepted" status
    status = status_from_bps_report(bps_report_with_failures)
    assert status is StatusEnum.accepted
