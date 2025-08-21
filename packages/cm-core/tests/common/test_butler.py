import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from lsst.cmservice.core.common.butler import ButlerFactory
from lsst.daf.butler import Butler
from lsst.daf.butler.tests import makeTestRepo


@pytest.fixture()
def mock_butler_environment(tmp_path: Any, monkeypatch: Any) -> None:
    """Create butler repo index values for the mock butler repos."""

    repo_mock_path = tmp_path / "repo" / "mock"
    repo_mock_path.mkdir(parents=True)

    repo_mockgres_butler_yaml = tmp_path / "repo" / "mockgres" / "butler+postgres.yaml"
    repo_mockgres_butler_yaml.parent.mkdir(parents=True)

    repo_yaml = """---
datastore:
  cls: lsst.daf.butler.datastores.chainedDatastore.ChainedDatastore
  datastores:
    -
      cls: "lsst.daf.butler.datastores.fileDatastore.FileDatastore"
      records:
        table: "file_datastore_records"
      root: <butlerRoot>
    -
      cls: "lsst.analysis.tools.interfaces.datastore.SasquatchDatastore"
      restProxyUrl: "http://mock/sasquatch-rest-proxy"
      namespace: "lsst.dm"
registry:
  db: postgresql://mockgres:5432/mockdb
"""
    repo_mockgres_butler_yaml.write_text(repo_yaml)

    daf_butler_repositories = {
        "/repo/mock": f"{repo_mock_path}",
        "/repo/mockgres": f"{repo_mockgres_butler_yaml}",
        "/doesnt/exist": f"{tmp_path}/no/such/path",
    }
    monkeypatch.setenv("DAF_BUTLER_REPOSITORIES", json.dumps(daf_butler_repositories))
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "accesskey")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secretkey")


@pytest.fixture()
def mock_butler_repo(tmp_path: Path, mock_butler_environment: Any) -> None:
    """Create mock butler repos using the ``makeTestRepo`` helper function"""

    _ = makeTestRepo(str(tmp_path / "repo" / "mock"))


@pytest.fixture
def mock_db_auth(monkeypatch: Any) -> None:
    """Fixture for a Butler DbAuth value.

    As YAML, the DbAuth can be written to a file, or serialized to JSON as
    stored as an environment variable.

    This will be consumed during Butler initialization.
    """
    mock_auth_yaml = """---
    -
      url: "postgresql://mockgres:5432/mockdb"
      username: mocker_mockerson
      password: letmein
    """
    mock_auth_json = json.dumps(yaml.safe_load(mock_auth_yaml))
    monkeypatch.setenv("LSST_DB_AUTH_CREDENTIALS", mock_auth_json)


def test_butler_factory(caplog: Any, mock_butler_repo: Any, mock_db_auth: Any) -> None:
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

    # The creation of the ButlerFactory should try and fail to connect to
    # the "mockgres" registry endpoint, as such a thing does not exist unless
    # an entire fixture database is set up.
    ...

    # Despite this, the ButlerFactory should know about the mockgres butler
    # and its auth config.
    rc = bf.get_butler_registry_config(label="/repo/mockgres")

    assert rc.connectionString.username == "mocker_mockerson"
    assert rc.connectionString.password == "letmein"

    # although asking for the butler from the factory will not be successful
    assert bf.get_butler("/repo/mockgres") is None

    # The application cannot load some butler configs with filestores that
    # depend on additional packages not available at runtime. These should
    # not cause the application to fail
    with pytest.raises(RuntimeError):
        _ = bf.get_butler_config(label="/repo/mockgres", without_datastore=False)

    # Unknown butlers fail quietly, but log the failure
    assert bf.get_butler("no/such/repo") is None

    # Butlers pointing to bad repo config files can't be loaded
    with pytest.raises(RuntimeError):
        _ = bf.get_butler_config(label="/doesnt/exist")


@pytest.mark.asyncio()
async def test_async_butler(mock_butler_repo: Any, mock_db_auth: Any) -> None:
    bf = ButlerFactory()
    assert bf is not None

    b = await bf.aget_butler("/repo/mock", collections=None)
    assert isinstance(b, Butler)
