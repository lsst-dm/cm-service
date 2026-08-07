from uuid import UUID

from sqlmodel import col, update
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.db.campaigns import Manifest
from lsst.cmservice.models.types import KindField


async def set_manifest_default_for_campaign(
    session: AsyncSession,
    *,
    manifest: Manifest | None = None,
    campaign_id: UUID | None = None,
    manifest_id: UUID | None = None,
    kind: KindField | None = None,
) -> None:
    """Set the manifest as the default for the given namespace."""
    if manifest is not None:
        campaign_id = manifest.namespace
        manifest_id = manifest.id
        kind = manifest.kind

    await session.exec(
        update(Manifest)
        .where(
            col(Manifest.namespace) == campaign_id,
            col(Manifest.kind) == kind,
            col(Manifest.default).is_(True),
        )
        .values(default=False)
    )
    await session.exec(update(Manifest).where(col(Manifest.id) == manifest_id).values(default=True))
