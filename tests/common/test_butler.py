import json
from typing import Any

import pytest

from lsst.cmservice.common.butler import get_butler_config
from lsst.cmservice.config import config
from lsst.daf.butler.registry import RegistryConfig


@pytest.fixture()
def mock_butler_environment(tmp_path: Any, monkeypatch: Any) -> None:
    repo_mock_path = tmp_path / "repo" / "mock"
    repo_mock_path.mkdir(parents=True)
    repo_mock_butler_yaml = repo_mock_path / "butler.yaml"

    repo_yaml = """---
datastore:
  cls: lsst.daf.butler.datastores.inMemoryDatastore.InMemoryDatastore
registry:
  db: "sqlite:///:memory:"
"""
    repo_mock_butler_yaml.write_text(repo_yaml)

    repo_mockgres_butler_yaml = repo_mock_path / "butler+postgres.yaml"

    repo_yaml = """---
datastore:
  cls: lsst.daf.butler.datastores.inMemoryDatastore.InMemoryDatastore
registry:
  db: postgresql://localhost:5432/mockdb
"""
    repo_mockgres_butler_yaml.write_text(repo_yaml)

    daf_butler_repositories = {
        "/repo/mock": f"{repo_mock_path}",
        "/repo/mockgres": f"{repo_mockgres_butler_yaml}",
        "mockbargo": "s3://bucket/prefix/object.yaml",
    }
    monkeypatch.setenv("DAF_BUTLER_REPOSITORIES", json.dumps(daf_butler_repositories))


@pytest.fixture
def mock_db_auth_file(tmp_path: Any, monkeypatch: Any) -> None:
    mock_auth_path = tmp_path / "db-auth.yaml"
    mock_auth_path.write_text("""---
    - url: postgresql://localhost:5432/mockdb
      username: mocker_mockerson
      password: letmein
    """)

    monkeypatch.setattr(config.butler, "authentication_file", str(mock_auth_path))


@pytest.mark.asyncio
async def test_butler_creation_without_db_auth_file(mock_butler_environment: Any) -> None:
    bc = await get_butler_config("/repo/mock", without_datastore=True)
    assert bc[".registry.db"] == "sqlite:///:memory:"


@pytest.mark.asyncio
async def test_butler_creation_with_db_auth_file(
    mock_butler_environment: Any, mock_db_auth_file: Any
) -> None:
    bc = await get_butler_config("/repo/mockgres", without_datastore=True)
    rc = RegistryConfig(bc)
    assert "mocker_mockerson" in rc.connectionString
