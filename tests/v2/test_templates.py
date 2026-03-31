"""Unit test module for template rendering using the jinja sandbox environment
with manifest templates as used by the campaign scheduler.
"""

from collections.abc import Generator
from textwrap import dedent

import pytest

from lsst.cmservice.common.templates import build_sandbox_and_render_templates

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


manifest_templates = [
    dedent("""\
        apiVersion: "io.lsst.cmservice/v1"
        kind: "campaign"
        metadata:
        name: {{ campaign_name }}
        spec:
            butlerSelector:
                instrument: lsstcam
                embargo: "false"
            lsstSelector:
                track: weekly
            wmsSelector:
                wms: htcondor
    """),
    dedent("""\
        apiVersion: "io.lsst.cmservice/v1"
        kind: "butler"
        metadata:
            name: "repo-main"
            labels:
                instrument: lsstcam
                embargo: "false"
        spec:
            repo: "/repo/main"
            predicates:
                - "instrument='LSSTCam'"
                - "skymap='lsst_cells_v1'"
                - "exposure > {{ obs_day | as_exposure(first_exposure) }}"
                - "exposure <= {{ obs_day | as_exposure(last_exposure) }}"
                - "exposure.observation_type IN ('science')"
                - "detector NOT IN ({{ bad_detectors | join(',') }})"
            collections:
                campaign_input:
                - LSSTCam/defaults
                campaign_public_output: u/lsstsvc1/dev/ci/${CAMPAIGN_NAME}
                campaign_output: u/lsstsvc1/dev/ci/${CAMPAIGN_NAME}/out
    """),
    dedent("""\
    apiVersion: "io.lsst.cmservice/v1"
    kind: "lsst"
    metadata:
        name: "continuous-integration"
        labels:
            track: weekly
    spec:
        lsst_version: {{ today | as_lsst_version }}
        lsst_distrib_dir: "/sdf/group/rubin/sw/{{ today | as_lsst_version}}"
    """),
]


@pytest.fixture
def template_generator() -> Generator[str]:
    return (t for t in manifest_templates)


async def test_custom_expressions(template_generator) -> None:
    expressions = {
        "campaign_name": "'test_simple_template'",
        "today": "datetime(year=2026, month=5, day=1)",
        "obs_day": "datetime(year=2025, month=7, day=23)",
        "first_exposure": 398,
        "last_exposure": 400,
        "bad_detectors": "[120, 121, 122, 78]",
    }
    x = await build_sandbox_and_render_templates(expressions, list(template_generator))

    assert "name: test_simple_template" in x[0]
    assert "exposure > 2025072300398" in x[1]
    assert "exposure <= 2025072300400" in x[1]
    assert "detector NOT IN (120,121,122,78)" in x[1]
    assert "lsst_version: w_2026_18" in x[2]
    ...
