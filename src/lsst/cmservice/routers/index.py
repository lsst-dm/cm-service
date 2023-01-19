from fastapi import APIRouter
from safir.metadata import Metadata, get_metadata

router = APIRouter()


@router.get(
    "/",
    description=(
        "Return metadata about the running application. Can also be used as a health check. This route"
        " is not exposed outside the cluster and therefore cannot be used by external clients."
    ),
    include_in_schema=False,
    response_model=Metadata,
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_index() -> Metadata:
    """GET ``/`` (the app's internal root).

    By convention, this endpoint returns only the application's metadata.
    """
    return get_metadata(
        package_name="lsst-cm-service",
        application_name="cm-service",
    )
