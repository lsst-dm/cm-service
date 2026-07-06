"""Unit test module for template rendering using the jinja sandbox environment
with manifest templates as used by the campaign scheduler.
"""

import re
from collections.abc import Generator
from itertools import islice
from textwrap import dedent
from uuid import uuid4

import pytest
from httpx import AsyncClient, codes

from lsst.cmservice.common.templates import build_sandbox_and_render_templates
from lsst.cmservice.models.api.schedules import ScheduleConfiguration
from lsst.cmservice.models.db.campaigns import Campaign, Manifest
from lsst.cmservice.models.db.schedules import CreateManifestTemplate

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


MANIFEST_TEMPLATES = [
    {
        "name": "A",
        "kind": "campaign",
        "manifest": dedent("""\
            apiVersion: "io.lsst.cmservice/v1"
            kind: "campaign"
            metadata:
                name: ${{ campaign_name }}
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
        "name": "A",
        "kind": "node",
        "manifest": dedent("""\
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
        "name": "A",
        "kind": "edge",
        "manifest": dedent("""\
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
        "name": "A",
        "kind": "butler",
        "manifest": dedent("""\
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
                    - "exposure > ${{ day_obs | as_exposure(first_exposure) }}"
                    - "exposure <= ${{ day_obs | as_exposure(last_exposure) }}"
                    - "exposure.observation_type IN ('science')"
                    - ${{ bad_detectors | sql_not_in(field="detector" )}}
                collections:
                    campaign_input:
                    - LSSTCam/defaults
                    campaign_public_output: u/lsstsvc1/dev/ci/${CAMPAIGN_NAME}
                    campaign_output: u/lsstsvc1/dev/ci/${CAMPAIGN_NAME}/out
        """),
    },
    {
        "name": "A",
        "kind": "lsst",
        "manifest": dedent("""\
            apiVersion: "io.lsst.cmservice/v1"
            kind: "lsst"
            metadata:
                name: "continuous-integration"
                labels:
                    track: weekly
            spec:
                lsst_version: ${{ today | as_lsst_version }}
                lsst_distrib_dir: "/sdf/group/rubin/sw/${{ today | as_lsst_version}}"
            """),
    },
]


@pytest.fixture
def template_generator() -> Generator[CreateManifestTemplate]:
    schedule_id = uuid4()
    return (
        CreateManifestTemplate(
            name=t["name"],
            kind=t["kind"],  # pyright: ignore[reportArgumentType]
            manifest=t["manifest"],
            schedule_id=schedule_id,
        )
        for t in MANIFEST_TEMPLATES
    )


async def test_custom_expressions(template_generator: Generator[CreateManifestTemplate]) -> None:
    context = ScheduleConfiguration(
        expressions={
            "campaign_name": "'test_simple_template'",
            "today": "datetime(year=2026, month=5, day=1)",
            "day_obs": "datetime(year=2025, month=7, day=23)",
            "first_exposure": "398",
            "last_exposure": "400",
            "bad_detectors": "[120, 121, 122, 78]",
        }
    )
    x = await build_sandbox_and_render_templates(context, list(template_generator))

    assert isinstance(x[0], Campaign)
    assert re.fullmatch(r"^test_simple_template_\d+$", x[0].name)

    assert isinstance(x[-3], Manifest)
    assert "exposure > 2025072300398" in x[-3].spec["predicates"]
    assert "exposure <= 2025072300400" in x[-3].spec["predicates"]
    assert "detector NOT IN (120,121,122,78)" in x[-3].spec["predicates"]

    assert isinstance(x[-2], Manifest)
    assert x[-2].spec.get("lsst_version") == "w_2026_18"

    # Ensure every campaign element created by the service layer has the same
    # correct namespace
    campaign_id = x[0].id
    for orm in islice(x, 1, None):
        assert orm.namespace == campaign_id


async def test_add_templates_to_schedule(aclient: AsyncClient) -> None:
    """Test the addition of new template manifests to an existing schedule."""
    x = await aclient.post("/v2/schedules", json={"name": str(uuid4())[0:8], "cron": "* * * * *"})
    assert x.status_code == codes.CREATED

    for template in MANIFEST_TEMPLATES:
        y = await aclient.post(f"""{x.headers["Self"]}/templates""", json=template)
        assert y.status_code == codes.CREATED

    y = await aclient.get(x.headers["Templates"])
    assert y.status_code == codes.OK
    assert len(y.json()) == len(MANIFEST_TEMPLATES)

    # Repeat the above, expecting new versions of each manifest
    for template in MANIFEST_TEMPLATES:
        y = await aclient.post(f"""{x.headers["Self"]}/templates""", json=template)
        assert y.status_code == codes.CREATED

    y = await aclient.get(x.headers["Templates"])
    assert y.status_code == codes.OK
    schedule_templates = y.json()
    assert len(schedule_templates) == len(MANIFEST_TEMPLATES) * 2
    version_1_templates = 0
    version_2_templates = 0
    for t in schedule_templates:
        if t["version"] == 1:
            version_1_templates += 1
        elif t["version"] == 2:
            version_2_templates += 1
        else:
            raise RuntimeError("No version other than 1 or 2 should exist in this test.")

    assert version_1_templates == version_2_templates


async def test_modify_existing_template(aclient: AsyncClient) -> None:
    """Test the addition of new template manifests to an existing schedule."""
    x = await aclient.post("/v2/schedules", json={"name": str(uuid4())[0:8], "cron": "* * * * *"})
    assert x.status_code == codes.CREATED

    for template in MANIFEST_TEMPLATES:
        y = await aclient.post(f"""{x.headers["Self"]}/templates""", json=template)
        assert y.status_code == codes.CREATED

    y = await aclient.get(x.headers["Templates"])
    assert y.status_code == codes.OK
    schedule_templates = y.json()
    assert len(schedule_templates) == len(MANIFEST_TEMPLATES)

    template_to_update = [c for c in schedule_templates if c["kind"] == "campaign"][0]
    template_id = template_to_update["id"]
    template_to_update["manifest"] = dedent("""\
        apiVersion: "io.lsst.cmservice/v1"
        kind: "campaign"
        metadata:
            name: ${{ campaign_name }}_aux
        spec:
            butlerSelector:
                instrument: lsstcam
                embargo: "true"
            lsstSelector:
                track: daily
            wmsSelector:
                wms: htcondor
    """)

    z = await aclient.put(
        f"""{x.headers["Self"]}/templates/{template_id}""",
        json=template_to_update,
    )
    assert z.status_code == codes.CREATED
