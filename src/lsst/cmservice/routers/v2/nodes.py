"""http routers for managing Node tables.

The /nodes endpoint supports a collection resource and single resources
representing node objects within CM-Service.
"""

from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Node, NodeModel
from ...db.manifests_v2 import ManifestWrapper
from ...db.session import db_session_dependency
from .campaigns import Campaign

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/nodes",
    tags=["nodes"],
)


@router.get(
    "/",
    summary="Get a list of nodes",
    response_model=list[NodeModel],
)
async def read_node_collection(
    request: Request,
    response: Response,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    session: AsyncSession = Depends(db_session_dependency),
):
    """Gets all nodes"""
    # TODO add paginated links to response header
    response.headers["Link"] = ""
    try:
        nodes = await session.exec(select(Node).offset(offset).limit(limit))
        return nodes.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{node_name}",
    summary="Get node detail",
    response_model=Node,
)
async def read_node_resource(
    request: Request,
    response: Response,
    node_name: str,
    session: AsyncSession = Depends(db_session_dependency),
):
    """Fetch a single node from the database given either the node id
    or its name.
    """
    s = select(Node)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if node_id := UUID(node_name):
            s = s.where(Node.id == node_id)
    except ValueError:
        s = s.where(Node.name == node_name)

    campaign = await session.exec(s)
    return campaign.one_or_none()


@router.post(
    "/",
    summary="Add a node resource",
    response_model=Node,
)
async def create_node_resource(
    request: Request,
    response: Response,
    manifest: ManifestWrapper,
    session: AsyncSession = Depends(db_session_dependency),
):
    # TODO should support query parameters that scope the namespace, such that
    #      response headers from a campaign-create operation can immediately
    #      follow a link to node-create for that campaign.

    # Validate the input by checking the "kind" of manifest is a node
    if manifest.kind != "node":
        raise HTTPException(status_code=422, detail="Nodes may only be created from a 'node' manifest")
    # and that the manifest includes any required fields, though this could
    # just as well be a try/except ValueError around `_.model_validate()`
    elif (node_name := manifest.metadata_.pop("name")) is None:
        raise HTTPException(status_code=400, detail="Nodes must have a name set in '.metadata.name'")

    # A node's spec must be a valid node spec
    # TODO match node with jsonschema and validate

    # A node must exist in the namespace of an existing campaign
    node_namespace: str = manifest.metadata_.pop("namespace")
    if node_namespace is None:
        raise HTTPException(
            status_code=400, detail="Nodes must have a namespace set in '.metadata.namespace'"
        )

    try:
        node_namespace_uuid = UUID(node_namespace)
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
    node_version = int(manifest.metadata_.pop("version", 0))

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
        configuration=manifest.spec,
    )

    # Put the node in the database
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return node
