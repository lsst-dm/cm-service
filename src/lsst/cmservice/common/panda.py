"""Module for PanDA operations within CM-Service"""

# This module should be primarily driven by configuration available in the
# config.panda settings object.

# Parts of this module may reimplement methods or functions originally found in
# `pandaclient`.

import datetime
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import httpx
from pandaclient.openidc_utils import decode_id_token

from ..config import config
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)
"""A module-level logger"""


@contextmanager
def http_client() -> Generator[httpx.Client]:
    """Generate a client session for panda API operations."""
    # Consistent with the pandaclient behavior, an "unverified" ssl context is
    # used with the session
    with httpx.Client(verify=False) as session:
        yield session


def refresh_token(url: str, data: dict[str, str]) -> str | None:
    """Refresh a panda auth token."""
    with http_client() as session:
        token_data: dict[str, str] = session.post(
            url=url, data=data, headers={"content-type": "application/x-www-form-urlencoded"}
        ).json()
    # TODO do what with the new token_data?
    # - write it out to the token file?
    #   Can't do that, it's going to be readonly
    # - update the configuration object?
    config.panda.id_token = token_data["id_token"]
    config.panda.refresh_token = token_data["refresh_token"]
    # - update the process environment?
    os.environ["PANDA_AUTH_ID_TOKEN"] = config.panda.id_token
    return config.panda.id_token


def get_token() -> str | None:
    """Load a panda auth token from a ``.token`` file in the appropriate
    location.

    TODO: make this async if necessary
    """

    # If a token has been added to the configuration object, use it instead of
    # loading one from disk
    try:
        if config.panda.id_token is None or config.panda.refresh_token is None:
            token_path = config.panda.config_root or os.getenv("PANDA_CONFIG_ROOT", "/")
            token_data = json.loads((Path(token_path) / ".token").read_text())
            config.panda.id_token = token_data["id_token"]
            config.panda.refresh_token = token_data["refresh_token"]
    except (FileNotFoundError, json.JSONDecodeError):
        logger.exception()
        return None

    # Determine whether the token should be renewed
    # The token expiry time is part of the encoded token
    decoded_token = decode_id_token(config.panda.id_token)

    # TODO if "exp" not in decoded_token: ...
    token_expiry = float(decoded_token["exp"])

    if (token_expiry - datetime.datetime.now(datetime.UTC).timestamp()) < config.panda.renew_after:
        if config.panda.auth_config_url is None:
            logger.error("There is no PanDA auth config url known to the service, cannot refresh token.")
            return token_data["id_token"]
        with http_client() as session:
            panda_auth_config = session.get(config.panda.auth_config_url).json()
            token_endpoint = session.get(panda_auth_config["oidc_config_url"]).json()["token_endpoint"]
        data = dict(
            client_id=panda_auth_config["client_id"],
            client_secret=panda_auth_config["client_secret"],
            grant_type="refresh_token",
            refresh_token=config.panda.refresh_token,
        )
        return refresh_token(token_endpoint, data)
    else:
        return config.panda.id_token
