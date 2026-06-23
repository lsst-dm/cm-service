"""Test the artifact-resource fetching support"""

from collections.abc import Generator
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid5

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from testcontainers.core.container import DockerContainer

from lsst.cmservice.machines.node import StepMachine
from lsst.cmservice.models.db.campaigns import Node
from lsst.resources import ResourcePath

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


@pytest.fixture(scope="module")
def s3mock_container() -> Generator[DockerContainer]:
    """Fixture starts a mock S3 object store with some buckets"""
    container = DockerContainer("adobe/s3mock:5.0.0")
    container.with_exposed_ports(9090)
    container.with_env("COM_ADOBE_TESTING_S3MOCK_STORE_INITIAL_BUCKETS", "mock-bucket")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="module")
def s3mock_config(
    s3mock_container: DockerContainer, tmp_path_m: Path, monkeypatch_module: pytest.MonkeyPatch
) -> Any:
    """Fixture creates aws-compatible config and credentials files for the mock
    object store.
    """
    port = s3mock_container.get_exposed_port(9090)
    aws_config = tmp_path_m / "config"
    aws_creds = tmp_path_m / "credentials"
    aws_config.write_text(
        dedent(f"""
        [profile mockbargo]
        request_checksum_calculation = when_required
        response_checksum_validation = when_required
        services = mockbargo-s3

        [services mockbargo-s3]
        s3 =
            endpoint_url = http://localhost:{port}
    """)
    )
    aws_creds.write_text(
        dedent(
            """
        [mockbargo]
        aws_access_key_id=NOT-A-REAL-ACCESS-KEY-ID
        aws_secret_access_key=NOT-A-REAL-SECRET-KEY
        """
        )
    )

    monkeypatch_module.setenv("AWS_CONFIG_FILE", str(aws_config))
    monkeypatch_module.setenv("AWS_SHARED_CREDENTIALS_FILE", str(aws_creds))


@pytest.fixture(scope="function")
def s3mock_objects(s3mock_config: Any) -> Any:
    """Fixture seeds object keys into the mock object store"""
    o = ResourcePath("s3://mockbargo@mock-bucket/external_config.yaml")
    o.write(b"abcdefghijklmnopqrstuvwxyz")


async def test_s3_resource_path(
    s3mock_objects: Any, aclient: AsyncClient, test_campaign_groups: str, session: AsyncSession
) -> None:
    """Tests a campaign step that needs to fetch external resources"""
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]

    # Fetch a step with no grouping
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    x = await aclient.patch(
        f"/v2/nodes/{node_id}",
        headers={"Content-Type": "application/json-patch+json"},
        json=[
            {
                "op": "add",
                "path": "/configuration/artifact",
                "value": {},
            },
            {
                "op": "add",
                "path": "/configuration/artifact/resources",
                "value": {"external_config.yaml": "s3://mockbargo@mock-bucket/external_config.yaml"},
            },
        ],
    )
    assert x.is_success
    node_v2 = x.json()["id"]

    # replace an existing node in the graph with the new one
    r = await aclient.put(
        f"/v2/campaigns/{campaign_id}/graph/nodes/{node_id}",
        params={"with-node": node_v2},
    )
    assert r.is_success

    node = await session.get_one(Node, node_v2)
    await session.commit()

    node_machine = StepMachine(o=node)
    await node_machine.trigger("prepare")

    # Assert that
    # 1. the "campaign" level static template has been rendered
    assert await (node_machine.artifact_path / "file_a.txt").exists()
    assert await (node_machine.artifact_path / "file_b.yaml").exists()

    # 2. the step level external resource has been fetched
    assert await (node_machine.artifact_path / "external_config.yaml").exists()
    assert "abcdef" in await (node_machine.artifact_path / "external_config.yaml").read_text()
