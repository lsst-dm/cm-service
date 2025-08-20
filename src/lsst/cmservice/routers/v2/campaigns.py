"""http routers for managing Campaign tables.

The /campaigns endpoint supports a collection resource and single resources
representing campaign objects within CM-Service.
"""

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Annotated, Literal, cast
from uuid import UUID, uuid5

from asgi_correlation_id import correlation_id
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Path, Query, Request, Response
from pydantic import UUID5
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import aliased
from sqlmodel import cast as sqlcast
from sqlmodel import col, distinct, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.enums import DEFAULT_NAMESPACE, ManifestKind, StatusEnum
from ...common.graph import append_node_to_graph, graph_from_edge_list_v2, graph_to_dict, insert_node_to_graph
from ...common.logging import LOGGER
from ...common.timestamp import element_time
from ...db.campaigns_v2 import (
    ActivityLog,
    Campaign,
    CampaignSummary,
    CampaignUpdate,
    Edge,
    Manifest,
    Node,
    NodeStatusSummary,
)
from ...db.manifests_v2 import CampaignManifest, ManifestRequest
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
    *,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
    include_hidden: Annotated[bool, Header(alias="CM-Admin-View")] = False,
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
        if not include_hidden:
            statement = statement.where(Campaign.id != DEFAULT_NAMESPACE)

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


@router.get("/{campaign_name_or_id}", response_model=Campaign, summary="Get campaign detail")
@router.head("/{campaign_name_or_id}", response_model=None, summary="Get campaign headers")
async def read_campaign_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name_or_id: str,
) -> Campaign | None:
    """Fetch a single campaign from the database given either the campaign id
    or its name.
    """
    s = select(Campaign)
    # The input could be a campaign UUID or it could be a literal name.
    try:
        if campaign_id := UUID(campaign_name_or_id):
            s = s.where(Campaign.id == campaign_id)
    except ValueError:
        s = s.where(Campaign.name == campaign_name_or_id)

    campaign = (await session.exec(s)).one_or_none()
    # set the response headers
    if campaign is None:
        raise HTTPException(status_code=404)

    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign.id))
    response.headers["Nodes"] = str(request.url_for("read_campaign_node_collection", campaign_id=campaign.id))
    response.headers["Edges"] = str(request.url_for("read_campaign_edge_collection", campaign_id=campaign.id))
    response.headers["Manifests"] = str(
        request.url_for("read_campaign_manifest_collection", campaign_id=campaign.id)
    )
    response.headers["Graph"] = str(request.url_for("read_campaign_graph", campaign_name=campaign.id))
    response.headers["Logs"] = str(request.url_for("read_campaign_activity_log", campaign_name=campaign.id))
    if request.method == "HEAD":
        return None
    else:
        return campaign


@router.get(
    "/{campaign_id}/summary",
    summary="Get campaign summary",
)
async def read_campaign_summary(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
) -> CampaignSummary:
    """Read a campaign summary resource, which consists of a subset of campaign
    information together with a count of active (i.e., in-graph) campaign nodes
    by status.
    """
    # FIXME this might be more effective as separate queries, one for the
    # campaign and a follow-up for the nodes / logs /etc. The single-query
    # join approach would be better served by a data structure that supports
    # a pivot operation, either with "crosstab" in the query or with a pandas
    # dataframe with the result. The approach used here, where the raw result
    # set is iterated in a way to "correctly" construct the response model,
    # is a bit contrived.

    # support a "summary" view that produces the count of nodes in each state
    # select
    #  cm.id, cm.name, cm.owner, cm.metadata, cm.status,
    #  nd.status as node_status,
    #  count(distinct nd.id) as node_count
    # from campaigns_v2 cm
    # join edges_v2 ed on cm.id=ed.namespace
    # join nodes_v2 nd on ed.namespace=nd.namespace
    # where cm.id = {campaign_id}
    # group by cm.id, nd.status
    s = (
        select(  # type: ignore[call-overload]
            col(Campaign.id),
            col(Campaign.name),
            col(Campaign.owner),
            col(Campaign.metadata_),
            col(Campaign.status),
            col(Node.status).label("node_status"),
            func.count(distinct(col(Edge.id))).label("edge_count"),
            func.count(distinct(col(Node.id))).label("node_count"),
            func.max(sqlcast(Node.metadata_["mtime"], INTEGER)).label("node_mtime"),
        )
        .outerjoin(Edge, col(Campaign.id) == Edge.namespace)
        .outerjoin(Node, col(Edge.namespace) == Node.namespace)
        .where(Campaign.id == campaign_id)
        .group_by(col(Campaign.id), col(Node.status))
    )
    r = await session.execute(s)
    try:
        first = next(r)
    except StopIteration:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    campaign_summary = CampaignSummary(
        **{
            f: first._mapping[f]
            for f in cast(str, filter(lambda x: x in Campaign.model_fields, first._mapping))
        },
    )

    # The summary will only report Node Status Summary for Campaign Nodes that
    # are part of the Campaign Graph, so if there are no edges in the campaign,
    # there will be none.
    if first._mapping["edge_count"] > 0:
        campaign_summary.node_summary.append(
            NodeStatusSummary(
                status=first._mapping["node_status"],
                count=first._mapping["node_count"],
                mtime=first._mapping["node_mtime"],
            )
        )

    for row in r:
        campaign_summary.node_summary.append(
            NodeStatusSummary(
                status=row._mapping["node_status"],
                count=row._mapping["node_count"],
                mtime=row._mapping["node_mtime"],
            )
        )
    return campaign_summary


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

    s = select(Campaign).with_for_update()

    try:
        if campaign_id := UUID(campaign_name):
            s = s.where(Campaign.id == campaign_id)
    except ValueError:
        s = s.where(Campaign.name == campaign_name)

    if (campaign := (await session.exec(s)).one_or_none()) is None:
        raise HTTPException(status_code=404, detail="No such campaign")

    # update the campaign with the patch data as a Merge operation
    update_data = patch_data.model_dump(exclude={"status"}, exclude_unset=True)
    campaign.sqlmodel_update(update_data)
    await session.commit()
    session.expunge(campaign)

    # If the patch data is requesting a status change, we will not affect that
    # directly, but defer it to a background task
    if patch_data.status is not None:
        if (request_id := correlation_id.get()) is None:
            raise HTTPException(status_code=500, detail="Cannot patch resource without a X-Request-Id")
        background_tasks.add_task(change_campaign_state, campaign, patch_data.status, request_id)
        # FIXME does this URL need to be campaign-scoped or does a general
        #       activity log URL make sense?
        response.headers["StatusUpdate"] = (
            f"""{request.url_for("read_campaign_activity_log", campaign_name=campaign.id)}"""
            f"""?request-id={request_id}"""
        ).strip()

    # set the response headers
    if campaign is not None:
        response.headers["Self"] = str(
            request.url_for("read_campaign_resource", campaign_name_or_id=campaign.id)
        )
        response.headers["Nodes"] = str(
            request.url_for("read_campaign_node_collection", campaign_id=campaign.id)
        )
        response.headers["Edges"] = str(
            request.url_for("read_campaign_edge_collection", campaign_id=campaign.id)
        )
    return campaign


# TODO head method and include a node count header
@router.get(
    "/{campaign_id}/nodes",
    summary="Get campaign Nodes",
)
async def read_campaign_node_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
    name: Annotated[str | None, Query()] = None,
) -> Sequence[Node]:
    """A paginated API returning a list of all Nodes in the namespace of a
    single Campaign.
    """

    statement = (
        select(Node)
        .where(Node.namespace == campaign_id)
        .order_by(col(Node.version).desc())
        .order_by(Node.metadata_["crtime"].asc().nulls_last())
        .offset(offset)
        .limit(limit)
    )

    if name is not None:
        statement = statement.where(col(Node.name) == name)

    nodes = await session.exec(statement)
    response.headers["Next"] = str(
        request.url_for(
            "read_campaign_node_collection",
            campaign_id=campaign_id,
        ).include_query_params(offset=(offset + limit), limit=limit),
    )
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign_id))
    return nodes.all()


@router.get(
    "/{campaign_id}/manifests",
    summary="Get campaign Manifests",
)
async def read_campaign_manifest_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
    limit: Annotated[int, Query(le=100)] = 10,
    offset: Annotated[int, Query()] = 0,
) -> Sequence[Manifest]:
    """A paginated API returning a list of all Manifests in the namespace of a
    single Campaign.
    """

    statement = (
        select(Manifest)
        .where(Manifest.namespace == campaign_id)
        .order_by(col(Manifest.version).desc())
        .order_by(Manifest.metadata_["crtime"].asc().nulls_last())
        .offset(offset)
        .limit(limit)
    )

    nodes = await session.exec(statement)
    response.headers["Next"] = str(
        request.url_for(
            "read_campaign_manifest_collection",
            campaign_id=campaign_id,
        ).include_query_params(offset=(offset + limit), limit=limit),
    )
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign_id))
    return nodes.all()


@router.get("/{campaign_id}/manifest/{kind}", summary="Get campaign Manifest by kind/name/version")
@router.get("/{campaign_id}/manifest/{kind}/{name}", summary="Get campaign Manifest by kind/name/version")
@router.get(
    "/{campaign_id}/manifest/{kind}/{name}/{version}", summary="Get campaign Manifest by kind/name/version"
)
async def read_campaign_manifest_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    manifest: Annotated[ManifestRequest, Path()],
) -> Manifest:
    """An API that returns a single specific Manifest as identified by some
    combination of its kind, name, and version.

    A manifest is returned from the campaign namespace which best matches:

    1. The specific matching Manifest of requested kind-name-version;
    2. The most recent (version-wise) available kind of manifest with a
       matching name;
    3. The most recent available kind of manifest with any name.
    """
    match manifest:
        case ManifestRequest(kind=kind, name=name, version=version) if kind is not None:
            s = (
                select(Manifest)
                .where(Manifest.kind == kind)
                .where(Manifest.namespace == manifest.campaign_id)
                .order_by(col(Manifest.version).desc())
                .limit(1)
            )
            if name is not None:
                s.where(Manifest.name == name)
            if version is not None:
                s.where(Manifest.version == version)
            r = (await session.exec(s)).one_or_none()
        case _:
            raise HTTPException(status_code=422)

    if r is None:
        raise HTTPException(status_code=404, detail="No such manifest could be located")

    response.headers["Self"] = str(request.url_for("read_single_manifest", manifest_name_or_id=r.id))
    return r


@router.get(
    "/{campaign_id}/edges",
    summary="Get campaign Edges",
)
async def read_campaign_edge_collection(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
    *,
    resolve_names: bool = False,
) -> Sequence[Edge]:
    """A paginated API returning a list of all Edges in the namespace of a
    single Campaign. This list of Edges can be used to construct the Campaign
    graph.
    """

    if resolve_names:
        source_nodes = aliased(Node, name="source")
        target_nodes = aliased(Node, name="target")
        statement = (
            select(  # type: ignore[call-overload]
                col(Edge.id).label("id"),
                col(Edge.name).label("name"),
                col(Edge.namespace).label("namespace"),
                col(source_nodes.name).label("source"),
                col(target_nodes.name).label("target"),
                col(Edge.configuration).label("configuration"),
            )
            .join_from(Edge, source_nodes, Edge.source == source_nodes.id)
            .join_from(Edge, target_nodes, Edge.target == target_nodes.id)
        )
    else:
        statement = select(Edge).order_by(col(Edge.name).asc().nulls_last())

    statement = statement.where(Edge.namespace == campaign_id)
    edges = await session.exec(statement)

    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign_id))
    return edges.all()


@router.delete(
    "/{campaign_id}/edges/{edge_name}",
    summary="Delete campaign edge",
    status_code=204,
)
async def delete_campaign_edge_resource(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
    edge_name: str,
) -> None:
    """Delete an edge resource from the campaign."""

    try:
        edge_id = UUID(edge_name)
    except ValueError:
        edge_id = uuid5(campaign_id, edge_name)

    s = select(Edge).with_for_update().where(Edge.id == edge_id)
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
    """An API to create a Campaign from an appropriate Manifest.

    If a duplicate campaign is created, the route returns the original campaign
    from the database with a 409 (conflict) status code.
    """

    campaign = Campaign.model_validate(
        dict(
            name=manifest.metadata_.name,
            metadata_=manifest.metadata_.model_dump(),
            # owner = ...  # TODO Get username from gafaelfawr # noqa: ERA001
        )
    )

    # A new campaign comes with a START and END node
    start_node = Node.model_validate(
        dict(
            name="START", namespace=campaign.id, kind=ManifestKind.start, metadata_={"crtime": element_time()}
        )
    )
    end_node = Node.model_validate(
        dict(name="END", namespace=campaign.id, kind=ManifestKind.end, metadata_={"crtime": element_time()})
    )

    try:
        # Put the campaign in the database
        session.add(campaign)
        session.add(start_node)
        session.add(end_node)
        await session.commit()
    except IntegrityError:
        # campaign already exists in the database, set the conflict status
        # response but allow the response to proceed
        logger.exception()
        await session.rollback()
        campaign = await session.get_one(Campaign, campaign.id)
        response.status_code = 409
    except Exception as e:
        logger.exception()
        raise HTTPException(status_code=500, detail=str(e))

    # set the response headers
    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign.id))
    response.headers["Nodes"] = str(request.url_for("read_campaign_node_collection", campaign_id=campaign.id))
    response.headers["Edges"] = str(request.url_for("read_campaign_edge_collection", campaign_id=campaign.id))
    response.headers["Graph"] = str(request.url_for("read_campaign_graph", campaign_name=campaign.id))
    response.headers["Activity"] = str(
        request.url_for("read_campaign_activity_log", campaign_name=campaign.id)
    )

    return campaign


@router.get(
    "/{campaign_name}/graph",
    status_code=200,
    summary="Construct and return a Campaign's graph of nodes",
)
async def read_campaign_graph(
    request: Request,
    response: Response,
    campaign_name: str,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
) -> Mapping:
    """Reads the graph resource for a campaign and returns its JSON represent-
    ation as serialized by the ``networkx.node_link_data()` function, i.e, the
    "node-link format".
    """

    # The input could be a campaign UUID or it could be a literal name.
    campaign_id: UUID | None
    try:
        campaign_id = UUID(campaign_name)
    except ValueError:
        s = select(Campaign.id).where(Campaign.name == campaign_name)
        campaign_id = (await session.exec(s)).one_or_none()

    if campaign_id is None:
        raise HTTPException(status_code=404, detail="No such campaign found.")

    # Fetch the Edges for the campaign
    statement = select(Edge).filter_by(namespace=campaign_id)
    edges = (await session.exec(statement)).all()

    # Organize the edges into a graph. The graph nodes are annotated with their
    # current database attributes according to the "simple" node view.
    graph = await graph_from_edge_list_v2(edges=edges, node_type=Node, session=session, node_view="simple")

    response.headers["Self"] = str(request.url_for("read_campaign_resource", campaign_name_or_id=campaign_id))
    return graph_to_dict(graph)


@router.get(
    "/{campaign_name}/logs",
    status_code=200,
    summary="Obtain a collection of Activity Log records for a Campaign.",
)
async def read_campaign_activity_log(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_name: str,
    request_id: Annotated[str | None, Query(validation_alias="request_id", alias="request-id")] = None,
) -> Sequence[ActivityLog]:
    """Returns the collection of Activity Log resources associated with a
    Campaign by its namespace. Optionally, a ``?request-id=...`` query param
    may constrain entries to specific client requests.
    """

    # The input could be a campaign UUID or it could be a literal name.
    campaign_id: UUID | None
    try:
        campaign_id = UUID(campaign_name)
    except ValueError:
        s = select(Campaign.id).where(Campaign.name == campaign_name)
        campaign_id = (await session.exec(s)).one_or_none()

    if campaign_id is None:
        raise HTTPException(status_code=404, detail="No such campaign found.")

    # Fetch the Activity Log entries for the campaign
    statement = select(ActivityLog).where(ActivityLog.namespace == campaign_id)
    if request_id is not None:
        statement = statement.filter(ActivityLog.metadata_["request_id"].astext == request_id)
    logs = (await session.exec(statement)).all()

    return logs


@router.put(
    "/{campaign_id}/graph/nodes/{node_0_id}",
    status_code=204,
    summary="Replace Node[0] with Node[1] in a Campaign Graph",
)
async def replace_node_in_graph(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    campaign_id: UUID5,
    node_0_id: UUID5,
    node_1_id: Annotated[UUID5, Query(validation_alias="node_1_id", alias="with-node")],
) -> None:
    """Replaces Node[0] in Campaign graph with provided Node[1]. The in and out
    edges for Node[0] are replaced with the same edges for Node[1]. The
    campaign must be in a "waiting" state for this operation to proceed, else
    a 409/Conflict is raised. A 404/Not Found is returned if any of the
    provided IDs are not found.

    This API is called with Node[0] as the target resource of the operation in
    the path and the Node[1] as a query parameter, e.g.,
    "http://.../graph/nodes/<node_0_id>?with-node=<node_1_id>"
    """
    # FIXME this should use a header param instead of a query param to be
    # consistent with other PUT apis.
    try:
        campaign = await session.get_one(Campaign, campaign_id)
        node_0 = await session.get_one(Node, node_0_id)
        node_1 = await session.get_one(Node, node_1_id)
    except NoResultFound:
        raise HTTPException(status_code=404)

    # Ensure the campaign is in a receptive state and that the subject nodes
    # are in its namespace.
    try:
        assert campaign.status in [StatusEnum.waiting, StatusEnum.paused]
    except AssertionError:
        raise HTTPException(
            status_code=409,
            detail=f"Graph for Campaign in status {campaign.status.name} cannot be modified.",
        )
    try:
        assert node_0.namespace == campaign.id
        assert node_1.namespace == campaign.id
    except AssertionError:
        raise HTTPException(
            status_code=409,
            detail="Alien nodes cannot be added to a campaign graph.",
        )

    # update edges that involve node_0 as a source
    s = select(Edge).with_for_update().where(Edge.source == node_0.id)
    edges = (await session.exec(s)).all()

    # Bail out if the Node isn't actually in the campaign graph. This could be
    # a no-op but we want to tell the caller they've made an error.
    if not len(edges):
        raise HTTPException(status_code=404, detail="Node_0 not in graph.")

    for edge in edges:
        edge.source = node_1.id
        edge.metadata_["mtime"] = element_time()

    # update edges that involve node_0 as a target
    s = select(Edge).with_for_update().where(Edge.target == node_0.id)
    edges = (await session.exec(s)).all()

    for edge in edges:
        edge.target = node_1.id
        edge.metadata_["mtime"] = element_time()

    await session.commit()

    response.headers["Edges"] = str(request.url_for("read_campaign_edge_collection", campaign_id=campaign.id))
    response.headers["Graph"] = str(request.url_for("read_campaign_graph", campaign_name=campaign.id))
    return None


@router.patch(
    "/{campaign_id}/graph/nodes/{node_0_id}",
    status_code=204,
    summary="Change Node[0] in a Campaign Graph by inserting or appending Node[1]",
)
async def update_node_in_graph(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    background_tasks: BackgroundTasks,
    campaign_id: UUID5,
    node_0_id: UUID5,
    node_1_id: Annotated[UUID5, Query(validation_alias="node_1_id", alias="add-node")],
    operation: Annotated[Literal["insert", "append"], Query()],
) -> None:
    """Updates Node[0] in a Campaign graph in terms of its relationship to a
    new Node[1]. This update can be an INSERT or an APPEND operation.

    In an INSERT operation, Node[1] is added to the graph immediately adjacent
    to Node[0]. All of Node[0]'s (outbound) edges are moved to Node[1] and
    an edge is created between Node[0] and Node[1].

    In an APPEND operation, Node[1] is added to the graph parallel to Node[0],
    preserving Node[0] but duplicating all its adjacencies as new edges for
    Node[1].

    The campaign must be in a mutable state and all Nodes must be in the same
    campaign namespace.
    """
    try:
        campaign = await session.get_one(Campaign, campaign_id)
        node_0 = await session.get_one(Node, node_0_id)
        node_1 = await session.get_one(Node, node_1_id)
    except NoResultFound:
        raise HTTPException(status_code=404)

    # Ensure the campaign is in a receptive state and that the subject nodes
    # are in its namespace.
    try:
        assert campaign.status in [StatusEnum.waiting, StatusEnum.paused]
    except AssertionError:
        raise HTTPException(
            status_code=409,
            detail=f"Graph for Campaign in status {campaign.status.name} cannot be modified.",
        )
    try:
        assert node_0.namespace == campaign.id
        assert node_1.namespace == campaign.id
    except AssertionError:
        raise HTTPException(
            status_code=409,
            detail="Alien nodes cannot be added to a campaign graph.",
        )

    # the append and insert operations are performed in library functions,
    # since this is reusable functionality that the node state machines will
    # also need to use for group-splitting operations.
    # TODO delegate to background task
    match operation:
        case "append":
            try:
                await append_node_to_graph(node_0_id, node_1_id, namespace=campaign_id, session=session)
            except NotImplementedError:
                # Invalid append operation
                raise HTTPException(400, detail=f"Nodes of kind {node_0.kind} cannot be APPENDED")
        case "insert":
            await insert_node_to_graph(node_0_id, node_1_id, namespace=campaign_id, session=session)
        case _:
            # not possible due to pydantic validation
            raise HTTPException(422)

    response.headers["Edges"] = str(request.url_for("read_campaign_edge_collection", campaign_id=campaign.id))
    response.headers["Graph"] = str(request.url_for("read_campaign_graph", campaign_name=campaign.id))
    return None


# TODO additional graph-node operations?
# - delete "/{campaign_id}/graph/nodes/{node_id}": remove a node from a graph,
#   self-healing by applying the node's predecessors to its adjacencies.
