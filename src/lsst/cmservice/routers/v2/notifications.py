"""http routers for managing Schedule tables.

These routes are RESTful endpoints that deal with resources and collections of
resources.

These routes depend upon app-level exception handling for returning 422, 404,
and 409 errors, so specific handling of these cases is implemented only if some
custom behavior is needed.
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.api.notifications import NotificationLabelManifest
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import ManifestKind

from ...common.logging import LOGGER
from ...config import config
from ...db.session import db_session_dependency

logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/notifications",
    tags=["notifications", "v2"],
)


@router.get(
    "/{label_name}",
    summary="Read an existing notification label",
)
async def read_notification_label_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    label_name: str,
) -> NotificationLabel:
    """Read a notification label resource. This API does not decrypt any
    secrets associated with the label.
    """
    # FIXME should probably use a return model that does not have a secret key
    # at all
    label = await session.get_one(NotificationLabel, label_name)
    ...
    return label


@router.post(
    "/",
    summary="Create a new notification label",
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_label_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    label_manifest: NotificationLabelManifest,
) -> None:
    """Create a notification label resource."""
    if config.notifications.fernet is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cannot create a label without a cryptography configuration",
        )
    elif label_manifest.kind is not ManifestKind.notification_label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This API accepts only notification_label manifests",
        )

    label = NotificationLabel(
        name=label_manifest.metadata_.name,
        kind=label_manifest.metadata_.kind,
        configuration={
            "filters": label_manifest.spec.filters
            or ["start:*:running", "end:running:*", "*:*:failed", "breakpoint:*:running"]
        },
        secret=config.notifications.fernet.encrypt(label_manifest.spec.secret_plaintext),
    )

    session.add(label)
    await session.commit()

    response.headers["Self"] = str(request.url_for("read_notification_label_resource", label_name=label.name))
