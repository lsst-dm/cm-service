import json
from pathlib import Path
from typing import Any

import pytest

from lsst.cmservice.common.butler import ButlerFactory
from lsst.cmservice.config import config
from lsst.daf.butler import Butler
from lsst.daf.butler.tests._testRepo import makeTestRepo


@pytest.fixture()
def mock_butler_environment(tmp_path: Any, monkeypatch: Any) -> None:
    """Create butler repo index values for the mock butler repos."""

    repo_mock_path = tmp_path / "repo" / "mock"
    repo_mock_path.mkdir(parents=True)

    repo_mockgres_butler_yaml = tmp_path / "repo" / "mockgres" / "butler+postgres.yaml"
    repo_mockgres_butler_yaml.parent.mkdir(parents=True)

    repo_yaml = """---
datastore:
  cls: lsst.daf.butler.datastores.inMemoryDatastore.InMemoryDatastore
registry:
  db: postgresql://mockgres:5432/mockdb
"""
    repo_mockgres_butler_yaml.write_text(repo_yaml)

    daf_butler_repositories = {
        "/repo/mock": f"{repo_mock_path}",
        # "/repo/mockgres": f"{repo_mockgres_butler_yaml}",
        # "mockbargo": "s3://bucket/prefix/object.yaml",
    }
    monkeypatch.setenv("DAF_BUTLER_REPOSITORIES", json.dumps(daf_butler_repositories))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "accesskey")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secretkey")


@pytest.fixture()
def mock_butler_repo(tmp_path: Path, mock_butler_environment: Any) -> None:
    """Create mock butler repos using the ``makeTestRepo`` helper function"""

    _ = makeTestRepo(str(tmp_path / "repo" / "mock"))


@pytest.fixture
def mock_db_auth_file(tmp_path: Any, monkeypatch: Any) -> None:
    mock_auth_path = tmp_path / "db-auth.yaml"
    mock_auth_path.write_text("""---
    - url: postgresql://mockgres:5432/mockdb
      username: mocker_mockerson
      password: letmein
    """)

    monkeypatch.setattr(config.butler, "authentication_file", str(mock_auth_path))


def test_butler_factory(mock_butler_repo: Any, mock_db_auth_file: Any) -> None:
    """Test butler factory with various butlers"""
    bf = ButlerFactory()
    assert bf is not None
    b = bf.get_butler("/repo/mock", collections=None)
    assert isinstance(b, Butler)

    cache_info = bf.get_butler_factory.cache_info()
    assert cache_info.hits == 1

    b2 = bf.get_butler("/repo/mock", collections=None)
    assert b is not b2  # these are separate clones of the same butler
    cache_info = bf.get_butler_factory.cache_info()
    assert cache_info.hits == 2  # the latest clone should have hit the cache
