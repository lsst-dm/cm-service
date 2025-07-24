"""http routers for managing Nodes.

The /nodes endpoint supports a collection resource and single resources
representing node objects within CM-Service.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid5

from deepdiff import Delta
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from pydantic import UUID5
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.enums import StatusEnum
from ...common.jsonpatch import JSONPatch, JSONPatchError, apply_json_patch
from ...common.logging import LOGGER
from ...common.timestamp import element_time
from ...db.campaigns_v2 import Campaign, Node
from ...db.manifests_v2 import NodeManifest
from ...db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/nodes",
    tags=["nodes", "v2"],
)


@router.get(
    "/",
    summary="Get a list of nodes",
)
async def read_nodes_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(le=100)] = 10,
    namespace: Annotated[UUID5 | None, Query(validation_alias="campaign_id", alias="campaign-id")] = None,
    node_name: Annotated[str | None, Query(validation_alias="node_name", alias="node-name")] = None,
) -> Sequence[Node]:
    """Fetches and returns all nodes known to the service.

    For campaign-scoped nodes, set the `campaign-id=` query parameter. The
    request can be further scoped with additional `node-name=` parameter.
    """
    statement = (
        select(Node).order_by(Node.metadata_["crtime"].desc().nulls_last()).offset(offset).limit(limit)
    )
    if namespace is not None:
        statement = statement.where(Node.namespace == namespace)
    if node_name is not None:
        statement = statement.where(Node.name == node_name)
    try:
        nodes = await session.exec(statement)
        response.headers["Next"] = (
            request.url_for("read_nodes_collection")
            .include_query_params(offset=(offset + limit), limit=limit)
            .__str__()
        )
        response.headers["Previous"] = (
            request.url_for("read_nodes_collection")
            .include_query_params(offset=(offset - limit), limit=limit)
            .__str__()
        )
        return nodes.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get("/{node_name}", response_model=Node, summary="Get single node detail")
@router.head("/{node_name}", response_model=None, summary="Get single node headers")
async def read_node_resource(
    request: Request,
    response: Response,
    node_name: str,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    namespace: Annotated[UUID5 | None, Query(validation_alias="campaign_id", alias="campaign-id")] = None,
    version: Annotated[int | None, Query()] = None,
) -> Node | None:
    """Fetch a single node from the database given either the node id or its
    name together with a namespace; if no version is provided, the "latest"
    version of the node is returned.
    """
    s = select(Node)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if node_id := UUID(node_name):
            s = s.where(Node.id == node_id)
    except ValueError:
        # node name by itself is not sufficient to identity a single node in
        # the database, so we must also constrain the request with the campaign
        # namespace or raise an error.
        if namespace is None:
            raise HTTPException(
                status_code=400, detail="Cannot locate Node by name alone. Try including `?campaign-id=...`"
            )
        s = s.where(Node.name == node_name).where(Node.namespace == namespace)

        if version is None:
            s = s.order_by(col(Node.version).desc())
        else:
            s = s.where(Node.version == version)

    node = (await session.exec(s.limit(1))).one_or_none()
    if node is None:
        raise HTTPException(status_code=404)
    response.headers["Self"] = request.url_for("read_node_resource", node_name=node.id).__str__()
    response.headers["Version"] = str(node.version)
    response.headers["Campaign"] = request.url_for(
        "read_campaign_resource", campaign_name_or_id=node.namespace
    ).__str__()

    if request.method == "HEAD":
        head_s = (
            select(Node.version)
            .where(Node.namespace == node.namespace)
            .where(Node.name == node.name)
            .order_by(col(Node.version).desc())
            .limit(1)
        )
        latest_node_version = (await session.exec(head_s)).one_or_none()
        response.headers["Latest"] = str(latest_node_version)
        response.headers["Namespace"] = str(node.namespace)
        response.headers["Name"] = node.name
        return None
    else:
        return node


@router.post(
    "/",
    summary="Add a node resource",
)
async def create_node_resource(
    request: Request,
    response: Response,
    manifest: NodeManifest,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> Node:
    node_name = manifest.metadata_.name
    node_namespace = manifest.metadata_.namespace

    try:
        node_namespace_uuid: UUID | None = UUID(node_namespace)
    except ValueError:
        # get the campaign ID by its name to use as a namespace
        node_namespace_uuid = (
            await session.exec(select(Campaign.id).where(Campaign.name == node_namespace))
        ).one_or_none()

    # it is an error if the provided namespace (campaign) does not exist
    # FIXME but this could also be handled by FK constraints
    if node_namespace_uuid is None:
        raise HTTPException(status_code=404, detail="Requested campaign namespace does not exist.")

    # A node must be a new version if name+namespace already exists
    # - check db for node as name+namespace, get current version and increment
    node_version = int(manifest.metadata_.version)

    s = (
        select(Node)
        .where(Node.name == node_name)
        .where(Node.namespace == node_namespace_uuid)
        .order_by(col(Node.version).desc())
        .limit(1)
    )
    previous_node = (await session.exec(s)).one_or_none()

    node_version = previous_node.version if previous_node else node_version
    node_version += 1
    node = Node(
        id=uuid5(node_namespace_uuid, f"{node_name}.{node_version}"),
        name=node_name,
        namespace=node_namespace_uuid,
        version=node_version,
        configuration=manifest.spec.model_dump(exclude_none=True),
        metadata_=manifest.metadata_.model_dump(exclude_none=True),
    )

    # Put the node in the database
    session.add(node)
    await session.commit()
    await session.refresh(node)
    response.headers["Self"] = request.url_for("read_node_resource", node_name=node.id).__str__()
    response.headers["Campaign"] = request.url_for(
        "read_campaign_resource", campaign_name_or_id=node.namespace
    ).__str__()
    return node


@router.patch(
    "/{node_name_or_id}",
    summary="Update node detail",
    status_code=202,
)
async def update_node_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    node_name_or_id: str,
    patch_data: Annotated[bytes, Body()] | Sequence[JSONPatch],
) -> Node:
    """Partial update method for nodes.

    A Nodes's spec or metadata may be updated with this PATCH operation. All
    updates to a Node creates a new version of the Node instead of
    updating an existing record in-place. This preserves history and keeps
    previous node versions available.

    A Node's name, id, kind, or namespace may not be modified by this
    method, and attempts to do so will produce a 4XX client error.

    This PATCH endpoint supports RFC6902 json-patch requests.

    Notes
    -----
    - This API always targets the latest version of a manifest when applying
      a patch. This requires and maintains a "linear" sequence of versions;
      it is not permissible to "patch" a previous version and create a "tree"-
      like history of manifests. For example, every manifest may be diffed
      against any previous version without having to consider branches.
    """
    use_rfc6902 = False
    use_deepdiff = False
    if request.headers["Content-Type"] == "application/json-patch+json":
        use_rfc6902 = True
    elif request.headers["Content-Type"] == "application/octet-stream":
        use_deepdiff = True
    else:
        raise HTTPException(status_code=406, detail="Unsupported Content-Type")

    s = select(Node).with_for_update()
    # The input could be a UUID or it could be a literal name.
    try:
        if _id := UUID(node_name_or_id):
            s = s.where(Node.id == _id)
    except ValueError:
        s = s.where(Node.name == node_name_or_id)

    # we want to order and sort by version, in descending order, so we always
    # fetch only the most recent version of manifest
    # FIXME this implies that when a node ID is provided, it should be an
    # error if it is not the most recent version.
    s = s.order_by(col(Node.version).desc()).limit(1)

    old_manifest = (await session.exec(s)).one_or_none()
    if old_manifest is None:
        raise HTTPException(status_code=404, detail="No such node")

    new_manifest = old_manifest.model_dump(by_alias=True)
    new_manifest["version"] += 1
    new_manifest["id"] = uuid5(new_manifest["namespace"], f"{new_manifest['name']}.{new_manifest['version']}")

    if use_rfc6902:
        for patch in patch_data:
            if TYPE_CHECKING:
                assert isinstance(patch, JSONPatch)
            try:
                apply_json_patch(patch, new_manifest)
            except JSONPatchError as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unable to process one or more patch operations: {e}",
                )
    elif use_deepdiff:
        if TYPE_CHECKING:
            assert isinstance(patch_data, bytes)
        new_manifest["configuration"] += Delta(patch_data)

    # create Manifest from new_manifest, add to session, and commit
    new_manifest["metadata"] = {"crtime": element_time()}
    new_manifest_db = Node.model_validate(new_manifest)
    new_manifest_db.status = StatusEnum.waiting
    session.add(new_manifest_db)
    await session.commit()

    response.headers["Self"] = request.url_for("read_node_resource", node_name=new_manifest_db.id).__str__()
    response.headers["Campaign"] = request.url_for(
        "read_campaign_resource", campaign_name_or_id=new_manifest_db.namespace
    ).__str__()

    return new_manifest_db
