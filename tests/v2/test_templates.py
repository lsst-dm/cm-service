"""Unit test module for template rendering using the jinja sandbox environment
with manifest templates as used by the campaign scheduler.
"""

from collections.abc import Generator
from itertools import islice
from textwrap import dedent
from uuid import uuid4

import pytest

from lsst.cmservice.common.templates import build_sandbox_and_render_templates
from lsst.cmservice.models.db.campaigns import Campaign, Manifest
from lsst.cmservice.models.db.schedules import ManifestTemplate

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


manifest_templates = [
    {
        "kind": "campaign",
        "template": dedent("""\
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
    },
    {
        "kind": "node",
        "template": dedent("""\
            apiVersion: io.lsst.cmservice/v1
            kind: node
            metadata:
                kind: step
                name: step_stage1
            spec:
                bps:
                    pipeline_yaml: ${DRP_PIPE_DIR}/pipelines/LSSTCam/DRP.yaml#stage1
                groups: null
        """),
    },
    {
        "kind": "edge",
        "template": dedent("""\
            apiVersion: io.lsst.cmservice/v1
            kind: edge
            metadata:
                name: xy-edge__STARTright-3left
            spec:
                source: START
                target: step_stage1
        """),
    },
    {
        "kind": "butler",
        "template": dedent("""\
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
    },
    {
        "kind": "lsst",
        "template": dedent("""\
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
    },
]


@pytest.fixture
def template_generator() -> Generator[ManifestTemplate]:
    schedule_id = uuid4()
    return (
        ManifestTemplate(kind=t["kind"], manifest=t["template"], schedule_id=schedule_id)  # pyright: ignore[reportArgumentType]
        for t in manifest_templates
    )


async def test_custom_expressions(template_generator: Generator[ManifestTemplate]) -> None:
    expressions = {
        "campaign_name": "'test_simple_template'",
        "today": "datetime(year=2026, month=5, day=1)",
        "obs_day": "datetime(year=2025, month=7, day=23)",
        "first_exposure": 398,
        "last_exposure": 400,
        "bad_detectors": "[120, 121, 122, 78]",
    }
    x = await build_sandbox_and_render_templates(expressions, list(template_generator))

    assert isinstance(x[0], Campaign)
    assert x[0].name == "test_simple_template"

    assert isinstance(x[2], Manifest)
    assert "exposure > 2025072300398" in x[2].spec["predicates"]
    assert "exposure <= 2025072300400" in x[2].spec["predicates"]
    assert "detector NOT IN (120,121,122,78)" in x[2].spec["predicates"]

    assert isinstance(x[3], Manifest)
    assert x[3].spec.get("lsst_version") == "w_2026_18"

    # Ensure every campaign element created by the service layer has the same
    # correct namespace
    campaign_id = x[0].id
    for orm in islice(x, 1, None):
        assert orm.namespace is campaign_id
