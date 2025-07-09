"""http routers for managing Campaign tables.

The /campaigns endpoint supports a collection resource and single resources
representing campaign objects within CM-Service.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Annotated
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import aliased
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.graph import graph_from_edge_list_v2, graph_to_dict
from ...common.logging import LOGGER
from ...common.timestamp import element_time
from ...db.campaigns_v2 import ActivityLog, Campaign, CampaignUpdate, Edge, Manifest, Node
from ...db.manifests_v2 import CampaignManifest
from ...db.session import db_session_dependency
from ...machines.tasks import change_campaign_state

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
    """A paginated API returning a list of all Campaigns known to the
    application, from newest to oldest.
    """
    try:
        statement = (
            select(Campaign)
            .order_by(Campaign.metadata_["crtime"].desc().nulls_last())
            .offset(offset)
            .limit(limit)
        )
        campaigns = await session.exec(statement)

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
        response.headers["Manifests"] = str(
            request.url_for("read_campaign_manifest_collection", campaign_name=campaign.id)
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
    background_tasks: BackgroundTasks,
    campaign_name: str,
    patch_data: CampaignUpdate,
) -> Campaign:
    """Partial update method for campaigns.

    Should primarily be used to set the status of a campaign, e.g., from
    waiting->running or running->paused.

    Rather than directly manipulating the campaign's record, a change to status
    uses a Background Task, which may or may not perform the requested update.
    This is why the method returns a 202; the user needs to check back "later"
    to see if the requested state change has occurred.

    Note
    ----
    For patching a Campaign status, this API accepts only RFC7396 "Merge-Patch"
    updates with the appropriate request header set.

    This route returns the Campaign subject to the PATCH, which may or may not
    reflect all the requested updates (subject to background task resolution).
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

    # update the campaign with the patch data as a Merge operation
    update_data = patch_data.model_dump(exclude={"status"}, exclude_unset=True)
    campaign.sqlmodel_update(update_data)
    await session.commit()
    session.expunge(campaign)

    # If the patch data is requesting a status change, we will not affect that
    # directly, but defer it to a background task
    if patch_data.status is not None:
        # TODO implement middleware to assign a request_id to every request
        request_id = uuid4()
        background_tasks.add_task(change_campaign_state, campaign, patch_data.status, request_id)
        response.headers["StatusUpdate"] = (
            f"""{request.url_for("read_campaign_activity_log", campaign_name_or_id=campaign.id)}"""
            f"""?request-id={request_id}"""
        ).strip()

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
    """A paginated API returning a list of all Nodes in the namespace of a
    single Campaign.
    """

    # The input could be a campaign UUID or it could be a literal name.
    # TODO this could just as well be a campaign query with a join to nodes
    statement = select(Node).order_by(Node.metadata_["crtime"].asc().nulls_last())

    try:
        if campaign_id := UUID(campaign_name):
            statement = statement.where(Node.namespace == campaign_id)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")
    statement = statement.offset(offset).limit(limit)
    nodes = await session.exec(statement)
    response.headers["Next"] = str(
        request.url_for(
            "read_campaign_node_collection",
            campaign_name=campaign_id,
        ).include_query_params(offset=(offset + limit), limit=limit),
    )
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign_id))
    return nodes.all()


@router.get(
    "/{campaign_name}/manifests",
    summary="Get campaign Manifests",
)
async def read_campaign_manifest_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
) -> Sequence[Manifest]:
    """A paginated API returning a list of all Manifests in the namespace of a
    single Campaign.
    """

    # The input could be a campaign UUID or it could be a literal name.
    statement = select(Manifest).order_by(Manifest.metadata_["crtime"].asc().nulls_last())

    try:
        if campaign_id := UUID(campaign_name):
            statement = statement.where(Manifest.namespace == campaign_id)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")
    statement = statement.offset(offset).limit(limit)
    nodes = await session.exec(statement)
    response.headers["Next"] = str(
        request.url_for(
            "read_campaign_manifest_collection",
            campaign_name=campaign_id,
        ).include_query_params(offset=(offset + limit), limit=limit),
    )
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign_id))
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
    """A paginated API returning a list of all Edges in the namespace of a
    single Campaign. This list of Edges can be used to construct the Campaign
    graph.
    """

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
        s = select(Edge).order_by(col(Edge.name).asc().nulls_last())
    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Edge.namespace == campaign_id)
    except ValueError:
        # FIXME get an id from a name
        raise HTTPException(status_code=422, detail="campaign_name must be a uuid")
    edges = await session.exec(s)

    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign_id))
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
    """An API to create a Campaign from an appropriate Manifest."""
    # Create a campaign spec from the manifest, delegating the creation of new
    # dynamic fields to the model validation method, -OR- create new dynamic
    # fields here.
    campaign_metadata = manifest.metadata_.model_dump()
    campaign_metadata |= {"crtime": element_time()}
    campaign = Campaign.model_validate(
        dict(
            name=campaign_metadata.pop("name"),
            metadata_=campaign_metadata,
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


@router.get(
    "/{campaign_name_or_id}/graph",
    status_code=200,
    summary="Construct and return a Campaign's graph of nodes",
)
async def read_campaign_graph(
    request: Request,
    response: Response,
    campaign_name_or_id: str,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> Mapping:
    """Reads the graph resource for a campaign and returns its JSON represent-
    ation as serialized by the ``networkx.node_link_data()` function, i.e, the
    "node-link format".
    """

    # The input could be a campaign UUID or it could be a literal name.
    campaign_id: UUID | None
    try:
        campaign_id = UUID(campaign_name_or_id)
    except ValueError:
        s = select(Campaign.id).where(Campaign.name == campaign_name_or_id)
        campaign_id = (await session.exec(s)).one_or_none()

    if campaign_id is None:
        raise HTTPException(status_code=404, detail="No such campaign found.")

    # Fetch the Edges for the campaign
    statement = select(Edge).filter_by(namespace=campaign_id)
    edges = (await session.exec(statement)).all()

    # Organize the edges into a graph. The graph nodes are annotated with their
    # current database attributes according to the "simple" node view.
    graph = await graph_from_edge_list_v2(edges=edges, node_type=Node, session=session, node_view="simple")

    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name=campaign_id))
    return graph_to_dict(graph)


@router.get(
    "/{campaign_name_or_id}/logs",
    status_code=200,
    summary="Obtain a collection of Activity Log records for a Campaign.",
)
async def read_campaign_activity_log(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name_or_id: str,
    request_id: Annotated[str | None, Query(validation_alias="request_id", alias="request-id")] = None,
) -> Sequence[ActivityLog]:
    """Returns the collection of Activity Log resources associated with a
    Campaign by its namespace. Optionally, a ``?request-id=...`` query param
    may constrain entries to specific client requests.
    """

    # The input could be a campaign UUID or it could be a literal name.
    campaign_id: UUID | None
    try:
        campaign_id = UUID(campaign_name_or_id)
    except ValueError:
        s = select(Campaign.id).where(Campaign.name == campaign_name_or_id)
        campaign_id = (await session.exec(s)).one_or_none()

    if campaign_id is None:
        raise HTTPException(status_code=404, detail="No such campaign found.")

    # Fetch the Activity Log entries for the campaign
    statement = select(ActivityLog).where(ActivityLog.namespace == campaign_id)
    if request_id is not None:
        statement = statement.filter(ActivityLog.metadata_["request_id"].astext == request_id)
    logs = (await session.exec(statement)).all()

    return logs
