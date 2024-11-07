import pytest
from httpx import AsyncClient

from lsst.cmservice import models
from lsst.cmservice.config import config

from .util_functions import (
    check_and_parse_response,
)


@pytest.mark.asyncio()
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
async def test_load_error_types_routes(client: AsyncClient) -> None:
    """Test `/job` API endpoint."""

    yaml_file_query = models.YamlFileQuery(
        yaml_file="examples/error_types.yaml",
    )

    response = await client.post(
        f"{config.prefix}/load/error_types",
        content=yaml_file_query.model_dump_json(),
    )
    error_types = check_and_parse_response(response, list[models.PipetaskErrorType])
    assert len(error_types) != 0

    rematch_query = models.RematchQuery(
        rematch=True,
    )
    response = await client.post(
        f"{config.prefix}/actions/rematch_errors",
        content=rematch_query.model_dump_json(),
    )
    matched_errors = check_and_parse_response(response, list[models.PipetaskError])
    assert len(matched_errors) == 0
