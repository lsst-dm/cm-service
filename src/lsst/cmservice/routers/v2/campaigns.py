"""http routers for managing Campaign tables.

The /campaigns endpoint supports a collection resource and single resources
representing campaign objects within CM-Service.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.logging import LOGGER
from ...db.campaigns_v2 import Campaign, CampaignUpdate, Edge, Node
from ...db.manifests_v2 import CampaignManifest
from ...db.session import db_session_dependency

# TODO should probably bind a logger to the fastapi app or something
logger = LOGGER.bind(module=__name__)


# Build the router
router = APIRouter(
    prefix="/campaigns",
    tags=["campaigns", "v2"],
)


@router.get(
    "/",
    summary="Get a list of campaigns",
)
async def read_campaign_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
) -> Sequence[Campaign]:
    """..."""
    try:
        campaigns = await session.exec(select(Campaign).offset(offset).limit(limit))

        response.headers["Next"] = str(
            request.url_for("read_campaign_collection").include_query_params(
                offset=(offset + limit), limit=limit
            )
        )
        if offset > 0:
            response.headers["Previous"] = str(
                request.url_for("read_campaign_collection").include_query_params(
                    offset=(offset - limit), limit=limit
                )
            )
        return campaigns.all()
    except Exception as msg:
        logger.exception()
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/{campaign_name}",
    summary="Get campaign detail",
)
async def read_campaign_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
) -> Campaign:
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
    if campaign is not None:
        response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign.id))
        response.headers["Nodes"] = str(
            request.url_for("read_campaign_node_collection", campaign_name=campaign.id)
        )
        response.headers["Edges"] = str(
            request.url_for("read_campaign_edge_collection", campaign_name=campaign.id)
        )
        return campaign
    else:
        raise HTTPException(status_code=404)


@router.patch(
    "/{campaign_name}",
    summary="Update campaign detail",
    status_code=202,
)
async def update_campaign_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    patch_data: CampaignUpdate,
) -> Campaign:
    """Partial update method for campaigns.

    Should primarily be used to set the status of a campaign, e.g., from
    waiting->ready, in order to trigger any validation rules contained in that
    transition.

    Another common use case would be to set status to "paused".

    This could be used to update a campaign's metadata, but otherwise the
    status is the only field available for modification, and even then there is
    not an imperative "change the status" command, rather a request to evolve
    the state of a campaign from A to B, which may or may not be successful.

    Rather than manipulating the campaign's record, a change to status should
    instead create a work item for the task processing queue for an executor
    to discover and attempt to act upon. Barring that, the work should be
    delegated to a Background Task. This is why the method returns a 202; the
    user needs to check back "later" to see if the requested state change has
    occurred.
    """
    use_rfc7396 = False
    use_rfc6902 = False
    mutable_fields = []
    if request.headers["Content-Type"] == "application/merge-patch+json":
        use_rfc7396 = True
        mutable_fields.extend(["owner", "status"])
    elif request.headers["Content-Type"] == "application/json-patch+json":
        use_rfc6902 = True
        mutable_fields.extend(["configuration", "metadata_"])
        raise HTTPException(status_code=501, detail="Not yet implemented.")
    else:
        raise HTTPException(status_code=406, detail="Unsupported Content-Type")

    if TYPE_CHECKING:
        assert use_rfc7396
        assert not use_rfc6902
    s = select(Campaign)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Campaign.id == campaign_id)
    except ValueError:
        s = s.where(Campaign.name == campaign_name)

    campaign = (await session.exec(s)).one_or_none()
    if campaign is None:
        raise HTTPException(status_code=404, detail="No such campaign")

    # update the campaign with the patch data
    update_data = patch_data.model_dump(exclude_unset=True)
    campaign.sqlmodel_update(update_data)
    session.add(campaign)
    await session.commit()
    await session.refresh(campaign)
    # set the response headers
    if campaign is not None:
        response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign.id))
        response.headers["Nodes"] = str(
            request.url_for("read_campaign_node_collection", campaign_name=campaign.id)
        )
        response.headers["Edges"] = str(
            request.url_for("read_campaign_edge_collection", campaign_name=campaign.id)
        )
    return campaign


@router.get(
    "/{campaign_name}/nodes",
    summary="Get campaign Nodes",
)
async def read_campaign_node_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
) -> Sequence[Node]:
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
    response.headers["Next"] = str(
        request.url_for(
            "read_campaign_node_collection",
            campaign_name=campaign_name,
        ).include_query_params(offset=(offset + limit), limit=limit),
    )
    # TODO Previous
    return nodes.all()


@router.get(
    "/{campaign_name}/edges",
    summary="Get campaign Edges",
)
async def read_campaign_edge_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    *,
    resolve_names: bool = False,
) -> Sequence[Edge]:
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
    status_code=204,
)
async def delete_campaign_edge_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    edge_name: str,
) -> None:
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
    return None


@router.post(
    "/",
    summary="Add a campaign resource",
)
async def create_campaign_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    manifest: CampaignManifest,
) -> Campaign:
    # Create a campaign spec from the manifest, delegating the creation of new
    # dynamic fields to the model validation method, -OR- create new dynamic
    # fields here.
    campaign = Campaign.model_validate(
        dict(
            name=manifest.metadata_.name,
            metadata_=manifest.metadata_.model_dump(),
            # owner = ...  # TODO Get username from gafaelfawr # noqa: ERA001
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
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign.id))
    response.headers["Nodes"] = str(
        request.url_for("read_campaign_node_collection", campaign_name=campaign.id)
    )
    response.headers["Edges"] = str(
        request.url_for("read_campaign_edge_collection", campaign_name=campaign.id)
    )

    return campaign
