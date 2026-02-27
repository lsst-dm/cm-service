from pathlib import Path

import pytest
from httpx import AsyncClient

from lsst.cmservice import models_
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
@pytest.mark.parametrize("api_version", ["v1"])
async def test_load_error_types_routes(client: AsyncClient, api_version: str) -> None:
    """Test `/job` API endpoint."""

    fixtures = Path(__file__).parent.parent / "fixtures" / "seeds"

    yaml_file_query = models_.YamlFileQuery(
        yaml_file=f"{fixtures}/error_types.yaml",
    )

    response = await client.post(
        f"{config.asgi.route_prefix}/{api_version}/load/error_types",
        content=yaml_file_query.model_dump_json(),
    )
    error_types = check_and_parse_response(response, list[models_.PipetaskErrorType])
    assert len(error_types) != 0

    rematch_query = models_.RematchQuery(
        rematch=True,
    )
    response = await client.post(
        f"{config.asgi.route_prefix}/{api_version}/actions/rematch_errors",
        content=rematch_query.model_dump_json(),
    )
    matched_errors = check_and_parse_response(response, list[models_.PipetaskError])
    assert len(matched_errors) == 0
