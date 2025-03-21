"""Module for PanDA operations within CM-Service"""

import datetime
import json
import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pandaclient.openidc_utils import decode_id_token

from ..config import config
from .logging import LOGGER

logger = LOGGER.bind(module=__name__)
"""A module-level logger"""


@contextmanager
def http_client() -> Generator[httpx.Client]:
    """Generate a client session for panda API operations."""
    transport = httpx.HTTPTransport(
        verify=config.panda.verify_host,
        retries=3,
    )
    with httpx.Client(transport=transport) as session:
        yield session


def refresh_panda_token(url: str, data: dict[str, str]) -> str | None:
    """Refresh a panda auth token.

    Notes
    -----
    This function updates the configuration parameters object as a side-effect
    while also returning the idtoken; callers may or may not use the return
    value

    Returns
    -------
    The current value of the PanDA id token as known by the configuration
    parameter, which may be `None` if no id token has yet been successfully
    determined.

    Raises
    ------
    HTTPStatusError
        Raised if the API call to a PanDA endpoint fails for status.

    json.JSONDecodeError
        Raised if a successful response body cannot be correctly parsed as JSON

    KeyError
        Raised if the response from a PanDA API does not contain an expected
        key.
    """
    with http_client() as session:
        response = session.post(
            url=url, data=data, headers={"content-type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()

    token_data: dict[str, str] = response.json()
    # with the new token...
    # - update the configuration object
    config.panda.id_token = token_data["id_token"]
    config.panda.refresh_token = token_data["refresh_token"]
    # - update the process environment
    os.environ["PANDA_AUTH_ID_TOKEN"] = config.panda.id_token
    # - update token expiry
    decoded_token = decode_id_token(config.panda.id_token)
    config.panda.token_expiry = float(decoded_token["exp"])  # type: ignore
    if TYPE_CHECKING:
        # the validation machinery of the pyantic field handles conversion
        # from float to datetime.
        assert isinstance(config.panda.token_expiry, datetime.datetime)
    return config.panda.id_token


def get_panda_token() -> str | None:
    """Fetch a panda id token from configuration or a token file as necessary.
    If a token does not exist or is near expiry, create or refresh a token.

    Returns
    -------
    str or None
        The string value of a panda id token or None if no such token exists or
        can be created.

    TODO: make this async if necessary, but the daemon is less sensitive to
          sync operations as long as they do not block indefinitely.

    Notes
    -----
    This function should be called at application startup to bootstrap an id
    token, and again before panda operations that may require the use of the
    id token, to ensure the validity within the token expiry time.

    The refresh operation never actually uses the current idtoken except to
    discover the expiry time. We don't actually need any bootstrap value for
    the idtoken if we start with a refresh token; the auth_config_url is
    determined from the panda url and the oidc VO.
    """

    # If no panda configuration exists in the application, return early
    if config.panda.url is None:
        return None

    # If a token has been added to the configuration object, use it instead of
    # loading one from disk
    try:
        if config.panda.refresh_token is None:
            token_data = json.loads((Path(config.panda.config_root) / ".token").read_text())
            config.panda.id_token = token_data["id_token"]
            config.panda.refresh_token = token_data["refresh_token"]
    except (FileNotFoundError, json.JSONDecodeError):
        logger.exception()
        return None

    now_utc = datetime.datetime.now(datetime.UTC)

    # Determine whether the token should be renewed
    # The token expiry time is part of the encoded token
    try:
        if config.panda.token_expiry is None:
            decoded_token = decode_id_token(config.panda.id_token)
            config.panda.token_expiry = float(decoded_token["exp"])  # type: ignore
        if TYPE_CHECKING:
            # the validation machinery of the pyantic field handles conversion
            # from float to datetime.
            assert isinstance(config.panda.token_expiry, datetime.datetime)
    except Exception:
        # NOTE: this should generally be an AttributeError but the 3rdparty
        #        function may change its operation.
        # If current id_token is None or otherwise not decodable, we will get a
        # new one from the refresh operation
        logger.exception()
        config.panda.token_expiry = now_utc

    if (config.panda.token_expiry - now_utc) < datetime.timedelta(config.panda.renew_after):
        if config.panda.auth_config_url is None:
            logger.error("There is no PanDA auth config url known to the service, cannot refresh token.")
            logger.warning("The current PanDA id token may be invalid.")
            return config.panda.id_token

        try:
            # TODO it is probably safe to cache these response tokens
            with http_client() as session:
                auth_config_response = session.get(config.panda.auth_config_url)
                auth_config_response.raise_for_status()
                panda_auth_config = auth_config_response.json()

                token_response = session.get(panda_auth_config["oidc_config_url"])
                token_response.raise_for_status()
                token_endpoint = token_response.json()["token_endpoint"]

                data = dict(
                    client_id=panda_auth_config["client_id"],
                    client_secret=panda_auth_config["client_secret"],
                    grant_type="refresh_token",
                    refresh_token=config.panda.refresh_token,
                )

            _ = refresh_panda_token(token_endpoint, data)
        except (httpx.HTTPStatusError, json.JSONDecodeError, KeyError):
            # Error classes could include http status, malformed responses, or
            # responses with missing keys, either in this function or in the
            # token refresh function.
            logger.exception()

    return config.panda.id_token
