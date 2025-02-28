"""http routers for managing Campaign tables.

The /campaigns endpoint supports a collection resource and single resources
representing campaign objects within CM-Service.
"""

from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Campaign, CampaignModel, Edge, EdgeResponseModel, Node
from ...db.manifests_v2 import ManifestWrapper
from ...db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns"],
)


@router.get(
    "/",
    summary="Get a list of campaigns",
    response_model=list[CampaignModel],
)
async def read_campaign_collection(
    response: Response,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    session: AsyncSession = Depends(db_session_dependency),
):
    """..."""
    try:
        campaigns = await session.exec(select(Campaign).offset(offset).limit(limit))
        return campaigns.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{campaign_name}",
    summary="Get campaign detail",
    response_model=Campaign,
)
async def read_campaign_resource(
    request: Request,
    response: Response,
    campaign_name: str,
    session: AsyncSession = Depends(db_session_dependency),
):
    """Fetch a single campaign from the database given either the campaign id
    or its name.
    """
    s = select(Campaign)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Campaign.id == campaign_id)
    except ValueError:
        s = s.where(Campaign.name == campaign_name)

    campaign = (await session.exec(s)).one_or_none()
    # set the response headers
    if campaign:
        response.headers["x-self"] = (
            f"""{request.url_for("read_campaign_resource", campaign_name=campaign.id)}"""
        )
        response.headers["x-nodes"] = (
            f"""{request.url_for("read_campaign_node_collection", campaign_name=campaign.id)}"""
        )
        response.headers["x-dges"] = (
            f"""{request.url_for("read_campaign_edge_collection", campaign_name=campaign.id)}"""
        )
    return campaign


@router.get(
    "/{campaign_name}/nodes",
    summary="Get campaign Nodes",
    response_model=list[Node],
)
async def read_campaign_node_collection(
    request: Request,
    response: Response,
    campaign_name: str,
    offset: int = 0,
    limit: int = Query(default=10, le=100),
    session: AsyncSession = Depends(db_session_dependency),
):
    # This is a convenience api that could also be `/nodes?campaign=...

    # The input could be a campaign UUID or it could be a literal name.
    # TODO this could just as well be a campaign query with a join to nodes
    s = select(Node)
    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Node.namespace == campaign_id)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")
    s = s.offset(offset).limit(limit)
    nodes = await session.exec(s)
    response.headers["next"] = (
        f"""{request.url_for("read_campaign_node_collection", campaign_name=campaign_name)}"""
        f"""?offset={offset + limit}&limit={limit}"""
    )
    return nodes.all()


@router.get(
    "/{campaign_name}/edges",
    summary="Get campaign Edges",
    response_model=list[EdgeResponseModel],
)
async def read_campaign_edge_collection(
    request: Request,
    response: Response,
    campaign_name: str,
    *,
    resolve_names: bool = False,
    session: AsyncSession = Depends(db_session_dependency),
):
    # This is a convenience api that could also be `/edges?campaign=...

    # The input could be a campaign UUID or it could be a literal name.
    # This is why raw SQL is better than ORMs
    # This is probably better off as two queries instead of a "complicated"
    # join.
    if resolve_names:
        source_nodes = aliased(Node, name="source")
        target_nodes = aliased(Node, name="target")
        s = (
            select(
                col(Edge.id).label("id"),
                col(Edge.name).label("name"),
                col(Edge.namespace).label("namespace"),
                col(source_nodes.name).label("source"),
                col(target_nodes.name).label("target"),
                col(Edge.configuration).label("configuration"),
            )  # type: ignore
            .join_from(Edge, source_nodes, Edge.source == source_nodes.id)
            .join_from(Edge, target_nodes, Edge.target == target_nodes.id)
        )
    else:
        s = select(Edge)
    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Edge.namespace == campaign_id)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")
    edges = await session.exec(s)
    return edges.all()


@router.delete(
    "/{campaign_name}/edges/{edge_name}",
    summary="Delete campaign edge",
)
async def delete_campaign_edge_resource(
    request: Request,
    response: Response,
    campaign_name: str,
    edge_name: str,
    session: AsyncSession = Depends(db_session_dependency),
):
    """Delete an edge resource from the campaign, using either name or id."""
    # If the campaign name is not a uuid, find the appropriate id
    try:
        campaign_id = UUID(campaign_name)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")

    try:
        edge_id = UUID(edge_name)
    except ValueError:
        edge_id = uuid5(campaign_id, edge_name)

    s = select(Edge).where(Edge.id == edge_id)
    edge_to_delete = (await session.exec(s)).one_or_none()

    if edge_to_delete is not None:
        await session.delete(edge_to_delete)
        await session.commit()
    else:
        raise HTTPException(status_code=404, detail="No such edge.")
    return {}


@router.post(
    "/",
    summary="Add a campaign resource",
    response_model=Campaign,
)
async def create_campaign_resource(
    request: Request,
    response: Response,
    manifest: ManifestWrapper,
    session: AsyncSession = Depends(db_session_dependency),
):
    # Validate the input by checking the "kind" of manifest is a campaign
    if manifest.kind != "campaign":
        raise HTTPException(
            status_code=422, detail="Campaigns may only be created from a 'campaign' manifest"
        )
    # and that the manifest includes any required fields, though this could
    # just as well be a try/except ValueError around `_.model_validate()`
    elif (campaign_name := manifest.metadata_.pop("name")) is None:
        raise HTTPException(status_code=400, detail="Campaigns must have a name set in '.metadata.name'")

    # Create a campaign spec from the manifest, delegating the creation of new
    # dynamic fields to the model validation method, -OR- create new dynamic
    # fields here.
    campaign = Campaign.model_validate(
        dict(
            name=campaign_name,
            metadata_=manifest.metadata_,
            # owner = ...  # TODO Get username from gafaelfawr
        )
    )

    # A new campaign comes with a START and END node
    start_node = Node.model_validate(dict(name="START", namespace=campaign.id))
    end_node = Node.model_validate(dict(name="END", namespace=campaign.id))
    # Put the campaign in the database
    session.add(campaign)
    session.add(start_node)
    session.add(end_node)
    await session.commit()
    await session.refresh(campaign)

    # set the response headers
    response.headers["X-Self"] = f"""{request.url_for("read_campaign_resource", campaign_name=campaign.id)}"""
    response.headers["X-Nodes"] = (
        f"""{request.url_for("read_campaign_node_collection", campaign_name=campaign.id)}"""
    )
    response.headers["X-Edges"] = (
        f"""{request.url_for("read_campaign_edge_collection", campaign_name=campaign.id)}"""
    )
    return campaign
