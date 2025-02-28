"""http routers for managing Edge tables.

The /edges endpoint supports a collection resource and single resources
representing edge objects within CM-Service.
"""

from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Edge, EdgeModel
from ...db.manifests_v2 import ManifestWrapper
from ...db.session import db_session_dependency
from .campaigns import Campaign

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/edges",
    tags=["edges"],
)


@router.get(
    "/",
    summary="Get a list of edges",
    response_model=list[EdgeModel],
)
async def read_collection(
    request: Request,
    response: Response,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    session: AsyncSession = Depends(db_session_dependency),
):
    """..."""
    try:
        edges = await session.exec(select(Edge).offset(offset).limit(limit))
        return edges.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{edge_name}",
    summary="Get edge detail",
    response_model=Edge,
)
async def read_edge_resource(
    request: Request,
    response: Response,
    edge_name: str,
    session: AsyncSession = Depends(db_session_dependency),
):
    """Fetch a single node from the database given either the node id
    or its name.
    """
    s = select(Edge)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if edge_id := UUID(edge_name):
            s = s.where(Edge.id == edge_id)
    except ValueError:
        s = s.where(Edge.name == edge_id)

    edge = (await session.exec(s)).one_or_none()
    if not edge:
        return {}
    response.headers["x-source"] = f"""{request.url_for("read_node_resource", node_name=edge.source)}"""
    response.headers["x-target"] = f"""{request.url_for("read_node_resource", node_name=edge.target)}"""
    return edge


@router.post(
    "/",
    summary="Add a edge resource",
    response_model=Edge,
)
async def create_edge_resource(
    request: Request,
    response: Response,
    manifest: ManifestWrapper,
    session: AsyncSession = Depends(db_session_dependency),
):
    # TODO should support query parameters that scope the namespace, such that
    #      response headers from a campaign-create operation can immediately
    #      follow a link to node-create for that campaign.

    # Validate the input by checking the "kind" of manifest is a node
    if manifest.kind != "edge":
        raise HTTPException(status_code=422, detail="Edges may only be created from a 'edge' manifest")
    # and that the manifest includes any required fields, though this could
    # just as well be a try/except ValueError around `_.model_validate()`
    elif (edge_name := manifest.metadata_.pop("name")) is None:
        # TODO generate an edge name; naming edges shouldn't
        #      really be a task required of campaign designers.
        raise HTTPException(status_code=400, detail="Edges must have a name set in '.metadata.name'")
    # A edge's spec must be a valid node spec
    # TODO match edge with jsonschema and validate
    elif (source_node := manifest.spec.pop("source")) is None:
        raise HTTPException(status_code=400, detail="Edges must have a source node'")
    elif (target_node := manifest.spec.pop("target")) is None:
        raise HTTPException(status_code=400, detail="Edges must have a target node'")

    # A edge must exist in the namespace of an existing campaign
    edge_namespace: str = manifest.metadata_.pop("namespace")
    if edge_namespace is None:
        raise HTTPException(status_code=422, detail="Edges must be created in a campaign namespace.")
    else:
        try:
            edge_namespace_uuid = UUID(edge_namespace)
        except ValueError:
            # get the campaign ID by its name to use as a namespace
            edge_namespace_uuid = (
                await session.exec(select(Campaign.id).where(Campaign.name == edge_namespace))
            ).one_or_none()

        # it is an error if the provided namespace (campaign) does not exist
        if edge_namespace_uuid is None:
            raise HTTPException(status_code=422, detail="Requested campaign namespace does not exist.")

    # an edge may specify the source and target nodes by name and version,
    # which means the UUID of these nodes is deterministic, or we could go to
    # the database to discover them + validate their existence.
    # TODO the edge spec should support mappings for source/target nodes but
    # for now assume the provided name has `.vN` appended to it already or
    # default to v1
    source_node = f"{source_node}.1" if "." not in source_node else source_node
    target_node = f"{target_node}.1" if "." not in target_node else target_node
    edge = Edge(
        id=uuid5(edge_namespace_uuid, f"{edge_name}"),
        name=edge_name,
        namespace=edge_namespace_uuid,
        source=uuid5(edge_namespace_uuid, f"{source_node}"),
        target=uuid5(edge_namespace_uuid, f"{target_node}"),
        configuration=manifest.spec,
    )

    # Put the node in the database
    # FIXME use upsert here, because edges are not versioned
    #       maybe the edge ID should be a product of its nodes if the name
    #       is not deterministic
    session.add(edge)
    await session.commit()
    await session.refresh(edge)
    response.headers["x-self"] = f"""{request.url_for("read_edge_resource", edge_name=edge.id)}"""
    return edge
