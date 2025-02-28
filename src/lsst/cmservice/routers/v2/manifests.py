"""http routers for managing Manifest tables.

The /manifests endpoint supports a collection resource and single resources
representing manifest objects within CM-Service.
"""

from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Manifest, ManifestModel, _default_campaign_namespace
from ...db.manifests_v2 import ManifestWrapper
from ...db.session import db_session_dependency
from .campaigns import Campaign

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/manifests",
    tags=["manifests"],
)


@router.get(
    "/",
    summary="Get a list of manifests",
    response_model=list[ManifestModel],
)
async def read_manifest_collection(
    request: Request,
    response: Response,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    session: AsyncSession = Depends(db_session_dependency),
):
    """Gets all manifests"""
    # TODO add paginated links to response header
    response.headers["Link"] = ""
    response.headers["x-next"] = (
        f"""{request.url_for("read_manifest_collection")}?offset={offset + limit}&limit={limit}"""
    )
    try:
        nodes = await session.exec(select(Manifest).offset(offset).limit(limit))
        return nodes.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{manifest_name}",
    summary="Get manifest detail",
    response_model=Manifest,
)
async def read_single_resource(
    request: Request,
    response: Response,
    manifest_name: str,
    session: AsyncSession = Depends(db_session_dependency),
):
    """Fetch a single manifest from the database given either an id or name"""
    s = select(Manifest)
    # The input could be a UUID or it could be a literal name.
    try:
        if _id := UUID(manifest_name):
            s = s.where(Manifest.id == _id)
    except ValueError:
        s = s.where(Manifest.name == manifest_name)

    campaign = await session.exec(s)
    return campaign.one_or_none()


@router.post(
    "/",
    summary="Add a manifest resource",
    response_model=dict,
)
async def create_one_or_more_resources(
    request: Request,
    response: Response,
    manifests: ManifestWrapper | list[ManifestWrapper],
    session: AsyncSession = Depends(db_session_dependency),
):
    # FIXME RETURNS: no idea

    # TODO should support query parameters that scope the namespace, such that
    #      response headers from a campaign-create operation can immediately
    #      follow a link to node-create for that campaign.

    # We could be given a single manifest or a list of them. In the singleton
    # case, wrap it in a list so we can treat everything equally
    if not isinstance(manifests, list):
        manifests = [manifests]

    # TODO for manifest in manifests...
    for manifest in manifests:
        # Validate the input by checking the "kind" of manifest.
        # The difference between a "manifest" and a "node" is iffy, but all we
        # want to assert here is that nodes, campaigns, and edges don't go in
        # the manifest table
        if manifest.kind in ["campaign", "node", "edge"]:
            raise HTTPException(status_code=422, detail=f"Manifests may not be a {manifest.kind} kind.")
        # and that the manifest includes any required fields, though this could
        # just as well be a try/except ValueError around `_.model_validate()`
        elif (_name := manifest.metadata_.pop("name")) is None:
            raise HTTPException(status_code=400, detail="Manifests must have a name set in '.metadata.name'")

        # TODO match node with jsonschema and validate

        # A manifest must exist in the namespace of an existing campaign
        # or the default namespace
        _namespace: str = manifest.metadata_.pop("namespace", None)
        if _namespace is None:
            _namespace_uuid = _default_campaign_namespace
        else:
            try:
                _namespace_uuid = UUID(_namespace)
            except ValueError:
                # get the campaign ID by its name to use as a namespace
                _namespace_uuid = (
                    await session.exec(select(Campaign.id).where(Campaign.name == _namespace))
                ).one_or_none()

            # it is an error if the provided namespace/campaign does not exist
            # FIXME but this could also be handled by FK constraints
            if _namespace_uuid is None:
                raise HTTPException(status_code=422, detail="Requested namespace does not exist.")

        # A node must be a new version if name+namespace already exists
        # - check db for node as name+namespace, get version and increment
        _version = int(manifest.metadata_.pop("version", 0))

        s = (
            select(Manifest)
            .where(Manifest.name == _name)
            .where(Manifest.namespace == _namespace_uuid)
            .order_by(col(Manifest.version).desc())
            .limit(1)
        )
        _previous = (await session.exec(s)).one_or_none()

        _version = _previous.version if _previous else _version
        _version += 1
        _manifest = Manifest(
            id=uuid5(_namespace_uuid, f"{_name}.{_version}"),
            name=_name,
            namespace=_namespace_uuid,
            version=_version,
            metadata_=manifest.metadata_,
            spec=manifest.spec,
        )

        # Put the node in the database
        session.add(_manifest)

    await session.commit()
    return {}
