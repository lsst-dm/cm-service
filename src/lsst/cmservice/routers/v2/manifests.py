"""http routers for managing Manifest tables.

The /manifests endpoint supports a collection resource and single resources
representing manifest objects within CM-Service.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.jsonpatch import JSONPatch, JSONPatchError, apply_json_patch
from ...common.logging import LOGGER
from ...common.timestamp import element_time
from ...db.campaigns_v2 import Campaign, Manifest
from ...db.manifests_v2 import ManifestModel
from ...db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/manifests",
    tags=["manifests", "v2"],
)


@router.get(
    "/",
    summary="Get a list of manifests",
)
async def read_manifest_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    offset: Annotated[int, Query()] = 0,
    limit: Annotated[int, Query(le=100)] = 10,
) -> Sequence[Manifest]:
    """Gets all manifests"""
    response.headers["Next"] = str(
        request.url_for("read_manifest_collection").include_query_params(offset=(offset + limit), limit=limit)
    )
    if offset > 0:
        response.headers["Previous"] = str(
            request.url_for("read_manifest_collection").include_query_params(
                offset=(offset - limit), limit=limit
            )
        )
    try:
        statement = (
            select(Manifest)
            .order_by(Manifest.metadata_["crtime"].desc().nulls_last())
            .offset(offset)
            .limit(limit)
        )
        nodes = await session.exec(statement)
        return nodes.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{manifest_name_or_id}",
    summary="Get manifest detail",
)
async def read_single_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    manifest_name_or_id: str,
    manifest_version: Annotated[int | None, Query(ge=0, alias="version")] = None,
) -> Manifest:
    """Fetch a single manifest from the database given either an id or name.

    When available, only the most recent version of the Manifest is returned,
    unless the version is provided as part of the query string.
    """
    s = select(Manifest)
    # The input could be a UUID or it could be a literal name.
    try:
        if _id := UUID(manifest_name_or_id):
            s = s.where(Manifest.id == _id)
    except ValueError:
        s = s.where(Manifest.name == manifest_name_or_id)

    if manifest_version is None:
        s = s.order_by(col(Manifest.version).desc()).limit(1)
    else:
        s = s.where(Manifest.version == manifest_version)

    manifest = (await session.exec(s)).one_or_none()
    if manifest is not None:
        response.headers["Self"] = str(
            request.url_for("read_single_resource", manifest_name_or_id=manifest.id)
        )
        return manifest
    else:
        raise HTTPException(status_code=404)


@router.post(
    "/",
    summary="Add a manifest resource",
    status_code=204,
)
async def create_one_or_more_manifests(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    manifests: ManifestModel | list[ManifestModel],
) -> None:
    # We could be given a single manifest or a list of them. In the singleton
    # case, wrap it in a list so we can treat everything equally
    if not isinstance(manifests, list):
        manifests = [manifests]

    for manifest in manifests:
        _name = manifest.metadata_.name

        # A manifest must exist in the namespace of an existing campaign
        # or the default namespace
        _namespace = manifest.metadata_.namespace

        try:
            _namespace_uuid = UUID(_namespace)
        except ValueError:
            # get the campaign ID by its name to use as a namespace
            # it is an error if the namespace/campaign does not exist
            # FIXME but this could also be handled by FK constraints
            if (
                _campaign_id := (
                    await session.exec(select(Campaign.id).where(Campaign.name == _namespace))
                ).one_or_none()
            ) is None:
                raise HTTPException(status_code=422, detail="Requested namespace does not exist.")
            _namespace_uuid = _campaign_id

        # A manifest must be a new version if name+namespace already exists
        # check db for manifest as name+namespace, get version and increment

        s = (
            select(Manifest)
            .where(Manifest.name == _name)
            .where(Manifest.namespace == _namespace_uuid)
            .order_by(col(Manifest.version).desc())
            .limit(1)
        )

        _previous = (await session.exec(s)).one_or_none()
        _version = _previous.version if _previous else manifest.metadata_.version
        _version += 1

        _manifest = Manifest(
            id=uuid5(_namespace_uuid, f"{_name}.{_version}"),
            name=manifest.metadata_.name,
            namespace=_namespace_uuid,
            kind=manifest.kind,
            version=_version,
            metadata_=manifest.metadata_.model_dump(exclude_none=True),
            spec=manifest.spec.model_dump(exclude_none=True),
        )

        # Put the node in the database
        session.add(_manifest)

    await session.commit()
    return None


@router.patch(
    "/{manifest_name_or_id}",
    summary="Update manifest detail",
    status_code=202,
)
async def update_manifest_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    manifest_name_or_id: str,
    patch_data: Sequence[JSONPatch],
) -> Manifest:
    """Partial update method for manifests.

    A Manifest's spec or metadata may be updated with this PATCH operation. All
    updates to a Manifest creates a new version of the Manifest instead of
    updating an existing record in-place. This preserves history and keeps
    previous manifest versions available.

    A Manifest's name, id, kind, or namespace may not be modified by this
    method, and attempts to do so will produce a 4XX client error.

    This PATCH endpoint supports only RFC6902 json-patch requests.

    Notes
    -----
    - This API always targets the latest version of a manifest when applying
      a patch. This requires and maintains a "linear" sequence of versions;
      it is not permissible to "patch" a previous version and create a "tree"-
      like history of manifests. For example, every manifest may be diffed
      against any previous version without having to consider branches.
    """
    use_rfc6902 = False
    if request.headers["Content-Type"] == "application/json-patch+json":
        use_rfc6902 = True
    else:
        raise HTTPException(status_code=406, detail="Unsupported Content-Type")

    if TYPE_CHECKING:
        assert use_rfc6902

    s = select(Manifest)
    # The input could be a UUID or it could be a literal name.
    try:
        if _id := UUID(manifest_name_or_id):
            s = s.where(Manifest.id == _id)
    except ValueError:
        s = s.where(Manifest.name == manifest_name_or_id)

    # we want to order and sort by version, in descending order, so we always
    # fetch only the most recent version of manifest
    # FIXME this implies that when a manifest ID is provided, it should be an
    # error if it is not the most recent version.
    s = s.order_by(col(Manifest.version).desc()).limit(1)

    old_manifest = (await session.exec(s)).one_or_none()
    if old_manifest is None:
        raise HTTPException(status_code=404, detail="No such campaign")

    new_manifest = old_manifest.model_dump(by_alias=True)
    new_manifest["version"] += 1
    new_manifest["id"] = uuid5(new_manifest["namespace"], f"{new_manifest['name']}.{new_manifest['version']}")

    for patch in patch_data:
        try:
            apply_json_patch(patch, new_manifest)
        except JSONPatchError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Unable to process one or more patch operations: {e}",
            )

    # create Manifest from new_manifest, add to session, and commit
    new_manifest["metadata"] |= {"crtime": element_time()}
    new_manifest_db = Manifest.model_validate(new_manifest)
    session.add(new_manifest_db)
    await session.commit()

    # TODO response headers
    return new_manifest_db
