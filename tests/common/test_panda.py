# ruff: noqa: F841

import base64
import datetime
import json
import os
from base64 import urlsafe_b64encode
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import pytest
from httpx import Response

from lsst.cmservice.common.logging import LOGGER
from lsst.cmservice.common.panda import get_token
from lsst.cmservice.config import config

logger = LOGGER.bind(module=__name__)


@pytest.fixture
def mock_id_token():
    """Create a mock PanDA id token that expires in 3 days."""
    expiry = int((datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=3)).timestamp())
    token_payload = {
        "sub": str(uuid4()),
        "kid": "rsa1",
        "iss": "https://panda-iam-doma.local/",
        "groups": ["Rubin"],
        "preferred_username": "mocker",
        "organisation_name": "PanDA-DOMA",
        "aud": str(uuid4()),
        "name": "Mocker Moccasin",
        "exp": expiry,
        "iat": expiry,
        "jti": str(uuid4()),
        "email": "mocker@mockalooza.io",
    }
    token_parts = [
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        urlsafe_b64encode(json.dumps(token_payload).encode()).strip(b"=").decode(),
        "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    ]
    yield ".".join(token_parts)


@pytest.fixture
def panda_env(monkeypatch, mock_id_token):
    config.panda.tls_url = "https://mock-panda.local:8443/server/panda"
    config.panda.auth_config_url = "https://mock-panda.local:8443/auth/Rubin_auth_config.json"
    config.panda.url = config.panda.tls_url
    config.panda.monitor_url = "https://mock-panda-bigmon.local:8443/"
    config.panda.id_token = mock_id_token
    config.panda.refresh_token = "xxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx."  # noqa: E501
    monkeypatch.setenv("PANDA_CONFIG_ROOT", "$HOME/.panda")
    monkeypatch.setenv("PANDA_URL_SSL", config.panda.tls_url)
    monkeypatch.setenv("PANDA_URL", config.panda.tls_url)
    monkeypatch.setenv("PANDACACHE_URL", config.panda.tls_url)
    monkeypatch.setenv("PANDAMON_URL", config.panda.monitor_url)
    monkeypatch.setenv("PANDA_AUTH", "oidc")
    monkeypatch.setenv("PANDA_AUTH_VO", "Rubin")
    monkeypatch.setenv("PANDA_BEHIND_REAL_LB", "true")
    monkeypatch.setenv("PANDA_USE_NATIVE_HTTPLIB", "1")


@pytest.mark.skip
def test_panda_token(panda_env):
    panda_config_home = config.panda.config_root or os.getenv("PANDA_CONFIG_ROOT", "/")

    # Load a panda token file
    token_file = Path(panda_config_home) / ".token"
    token_data = json.loads(token_file.read_text())

    # tokens
    refresh_token = token_data["refresh_token"]
    id_token = token_data["id_token"]

    # Details of the token can be decoded from the token body, but this is not
    # used in the refresh action.
    enc = id_token.split(".")[1]
    enc += "=" * (-len(enc) % 4)
    _ = json.loads(base64.urlsafe_b64decode(enc.encode()))

    # The authurl to use for token ops is derived from the panda base url
    url_parts = urlparse(config.panda.url)
    auth_url = "{url_parts.scheme}://{url_parts.hostname}:{url_parts.port}/auth/{config.panda.virtual_organization}_auth_config.json"

    # the pandaclient uses a filesystem cache to cache the results of a dip to
    # the auth config for up to 1 hour. Otherwise, accesses the url, writes the
    # resulting text to a file, then reads it back in.
    # the contents of this file are
    # {
    #  "client_secret": "xxx",
    #  "audience": "https://pandaserver-doma.cern.ch",
    #  "client_id": "uuid",
    #  "oidc_config_url": "https://panda-iam-doma.cern.ch/.well-known/openid-configuration",
    #  "vo": "Rubin", "no_verify": "True", "robot_ids": "NONE"
    # }
    #
    # The refresh token operation is assembled using
    # - `client_id` and `client_secret` from the auth config endpoint
    # - `token_endpoint` from the oidc_config_url,
    #    e.g., https://panda-iam-doma.cern.ch/.well-known/openid-configuration
    # - `refresh_token_string` from the current token file
    # self.refresh_token(
    #   endpoint_config["token_endpoint"],
    #   auth_config["client_id"],
    #   auth_config["client_secret"],
    #   refresh_token_string
    # )
    token = get_token()


@pytest.fixture
def auth_config_mock_response():
    yield {
        "client_secret": "XXXxxXxXxXXxXXXXxXxxxXXXXxxxXXXxxxXXX-XXXxxxxXxxxxxxXxxxXX",
        "audience": "https://pandaserver-doma.local",
        "client_id": "00000000-0000-0000-0000-000000000000",
        "oidc_config_url": "https://panda-iam-doma.local/.well-known/openid-configuration",
        "vo": "Rubin",
        "no_verify": "True",
        "robot_ids": "NONE",
    }


@pytest.fixture
def oidc_config_mock_response():
    response_fixture = Path(__file__).parent.parent / "fixtures" / "panda" / "oidc_config_response.json"
    yield response_fixture.read_text()


def test_get_panda_token(
    respx_mock, panda_env, mock_id_token, auth_config_mock_response, oidc_config_mock_response
):
    # Tests loading a panda token that has not been expired
    auth_config_mock = respx_mock.get(config.panda.auth_config_url)
    auth_config_mock.return_value = Response(200, json=auth_config_mock_response)
    oidc_config_mock = respx_mock.get("https://panda-iam-doma.local/.well-known/openid-configuration")
    oidc_config_mock.return_value = Response(200, text=oidc_config_mock_response)
    token_endpoint_mock = respx_mock.post("https://panda-iam-doma.local/token")
    token_endpoint_mock.return_value = Response(
        200, json={"id_token": mock_id_token, "refresh_token": config.panda.refresh_token}
    )

    token = get_token()
