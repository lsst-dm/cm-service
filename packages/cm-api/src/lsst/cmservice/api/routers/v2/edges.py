"""http routers for managing Edges.

The /edges endpoint supports a collection resource and single resources
representing edge objects within CM-Service.
"""

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.core.common.logging import LOGGER
from lsst.cmservice.core.db.campaigns_v2 import Campaign, Edge
from lsst.cmservice.core.db.manifests_v2 import EdgeManifest
from lsst.cmservice.core.db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/edges",
    tags=["edges", "v2"],
)


@router.get(
    "/",
    summary="Get a list of edges",
)
async def read_edges_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(le=100)] = 10,
) -> Sequence[Edge]:
    """Fetches and returns all edges known to the service.

    Notes
    -----
    For campaign-scoped edges, one should use the /campaigns/{}/edges route.
    """
    try:
        statement = select(Edge).order_by(col(Edge.name).desc()).offset(offset).limit(limit)
        edges = await session.exec(statement)
        response.headers["Next"] = (
            request.url_for("read_edges_collection")
            .include_query_params(offset=(offset + limit), limit=limit)
            .__str__()
        )
        response.headers["Previous"] = (
            request.url_for("read_edges_collection")
            .include_query_params(offset=(offset - limit), limit=limit)
            .__str__()
        )
        return edges.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{edge_name}",
    summary="Get edge detail",
)
async def read_edge_resource(
    request: Request,
    response: Response,
    edge_name: str,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> Edge:
    """Fetch a single edge from the database given the edge name or id.

    The response headers include links to the connected nodes, the associated
    campaign, and to the graph with which the edge is associated (i.e., the
    collection of all campaign edges).
    """
    s = select(Edge)
    # The input could be UUID or a literal name.
    try:
        if edge_id := UUID(edge_name):
            s = s.where(Edge.id == edge_id)
    except ValueError:
        s = s.where(Edge.name == edge_name)

    edge = (await session.exec(s)).one_or_none()
    if edge is None:
        raise HTTPException(status_code=404)
    response.headers["Self"] = request.url_for("read_edge_resource", edge_name=edge.id).__str__()
    response.headers["Source"] = request.url_for("read_node_resource", node_name=edge.source).__str__()
    response.headers["Target"] = request.url_for("read_node_resource", node_name=edge.target).__str__()
    response.headers["Campaign"] = request.url_for(
        "read_campaign_resource", campaign_name_or_id=edge.namespace
    ).__str__()
    response.headers["Graph"] = request.url_for(
        "read_campaign_edge_collection", campaign_id=edge.namespace
    ).__str__()
    return edge


@router.post(
    "/",
    summary="Add a edge resource",
)
async def create_edge_resource(
    request: Request,
    response: Response,
    manifest: EdgeManifest,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> Edge:
    """Creates a new edge from a Manifest.

    The Manifest must be of type "edge" and include a campaign namespace in its
    metadata. If an edge name is not provided, a random name is assigned.

    ```
    ---
    apiVersion: "io.lsst.cmservice/v1"
    kind: edge
    metadata:
        name: {edge name}
        namespace: {campaign uuid}
    spec:
        source: {node name or id}
        target: {node name or id}
    ```
    """
    edge_name = manifest.metadata_.name
    source_node = manifest.spec.source
    target_node = manifest.spec.target

    # A edge must exist in the namespace of an existing campaign
    try:
        edge_namespace_uuid: UUID | None = UUID(manifest.metadata_.namespace)
    except ValueError:
        # get the campaign ID by its name to use as a namespace
        edge_namespace_uuid = (
            await session.exec(select(Campaign.id).where(Campaign.name == manifest.metadata_.namespace))
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
    # TODO support node id in spec
    source_node = f"{source_node}.1" if "." not in source_node else str(source_node)
    target_node = f"{target_node}.1" if "." not in target_node else str(target_node)

    # An edge's name is not necessarily deterministic, so for the ID we'll
    # construct a UUID5 that involves the nodes instead
    edge_id = uuid5(edge_namespace_uuid, f"{source_node}->{target_node}")

    edge = Edge(
        id=edge_id,
        name=edge_name,
        namespace=edge_namespace_uuid,
        source=uuid5(edge_namespace_uuid, source_node),
        target=uuid5(edge_namespace_uuid, target_node),
        metadata_=manifest.metadata_.model_dump(exclude_none=True),
        configuration=manifest.spec.model_dump(exclude_none=True),
    )

    # The merge operation is effectively an upsert should an edge matching the
    # id already exist
    edge = await session.merge(edge, load=True)
    await session.commit()

    response.headers["Self"] = request.url_for("read_edge_resource", edge_name=edge.id).__str__()
    response.headers["Source"] = request.url_for("read_node_resource", node_name=edge.source).__str__()
    response.headers["Target"] = request.url_for("read_node_resource", node_name=edge.target).__str__()
    response.headers["Campaign"] = request.url_for(
        "read_campaign_resource", campaign_name_or_id=edge.namespace
    ).__str__()
    response.headers["Graph"] = request.url_for(
        "read_campaign_edge_collection", campaign_id=edge.namespace
    ).__str__()
    return edge


@router.delete(
    "/{edge_id}",
    summary="Delete edge",
    status_code=204,
)
async def delete_edge_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    edge_id: UUID,
) -> None:
    """Delete an edge given its id."""
    s = select(Edge).with_for_update().where(Edge.id == edge_id)
    edge_to_delete = (await session.exec(s)).one_or_none()

    if edge_to_delete is None:
        raise HTTPException(status_code=404, detail="No such edge.")

    await session.delete(edge_to_delete)
    await session.commit()
    return None
