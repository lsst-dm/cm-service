# ruff: noqa: F841

import datetime
import json
from base64 import urlsafe_b64encode
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from httpx import Response

from lsst.cmservice.common.logging import LOGGER
from lsst.cmservice.common.panda import get_panda_token
from lsst.cmservice.config import config

logger = LOGGER.bind(module=__name__)


@pytest.fixture
def mock_id_token() -> Generator[str]:
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
def panda_env(monkeypatch: Any, mock_id_token: Any) -> None:
    config.panda.tls_url = "https://mock-panda.local:8443/server/panda"
    config.panda.monitor_url = "https://mock-panda-bigmon.local:8443/"
    config.panda.refresh_token = "xxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx."  # noqa: E501


@pytest.fixture
def auth_config_mock_response() -> Generator[dict[str, str]]:
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
def oidc_config_mock_response() -> Generator[str]:
    response_fixture = Path(__file__).parent.parent / "fixtures" / "panda" / "oidc_config_response.json"
    yield response_fixture.read_text()


def test_get_panda_token(
    respx_mock: Any,
    panda_env: Any,
    mock_id_token: Any,
    auth_config_mock_response: Any,
    oidc_config_mock_response: Any,
) -> None:
    # Tests loading a panda token that has not been expired
    auth_config_mock = respx_mock.get(config.panda.auth_config_url)
    auth_config_mock.return_value = Response(200, json=auth_config_mock_response)
    oidc_config_mock = respx_mock.get("https://panda-iam-doma.local/.well-known/openid-configuration")
    oidc_config_mock.return_value = Response(200, text=oidc_config_mock_response)
    token_endpoint_mock = respx_mock.post("https://panda-iam-doma.local/token")
    token_endpoint_mock.return_value = Response(
        200, json={"id_token": mock_id_token, "refresh_token": config.panda.refresh_token}
    )

    token = get_panda_token()
    # TODO make assertions about token
