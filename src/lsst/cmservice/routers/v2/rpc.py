"""Module implementing route handlers for RPC (verb-based) APIs."""

from typing import Annotated
from uuid import UUID

from anyio import to_thread
from asgi_correlation_id import correlation_id
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import UUID5, BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from ...common.daemon_v2 import assemble_campaign_graph, daemon_consider_campaign, daemon_process_node
from ...common.enums import StatusEnum
from ...common.graph import processable_graph_nodes
from ...common.logging import LOGGER
from ...db.campaigns_v2 import Campaign, Node
from ...db.session import db_session_dependency

logger = LOGGER.bind(module=__name__)

# Build the router
router = APIRouter(
    prefix="/rpc",
    tags=["rpc", "v2"],
)


async def fetch_by_id[T](session: AsyncSession, model: type[T], id: UUID) -> T:
    """Uses the supplied session to check whether the provided ID exists as a
    primary key value for the specified model.

    Returns the object associated with the key if the ID is found in the model
    table, otherwise raises a 404 HTTP Exception, so should only be used in API
    Routes.
    """

    result = await session.get(model, id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return result


class ProcessTarget(BaseModel):
    """A validating model for parameters used by the process RPC."""

    campaign_id: UUID5 | None = Field(default=None)
    node_id: UUID5 | None = Field(default=None)
    namespace: UUID5 | None = Field(default=None)


@router.post(
    "/process",
    summary="Attempt to evolve a campaign or node",
    status_code=status.HTTP_202_ACCEPTED,
)
async def rpc_process_campaign_or_node(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(db_session_dependency)],
    target: ProcessTarget,
) -> None:
    """Process a campaign or node along its happy path. This is equivalent to
    a single iteration of a daemon loop addressing either a campaign or a node.

    In the case of a campaign, all available nodes are considered; in the case
    of a node, only the specified node is processed.

    Callers of this RPC API do not specify a desired target state in either a
    forward or reverse fashion. Instead, the processing methods determine the
    specific work needed next in the target's graph or state machine.

    Targets in a terminal state (such as "failed" or "accepted") will not be
    modified by this API.

    The parameters for this API are always taken from the Request Body. If
    multiple IDs are in the Request Body, the API proceeds with the more
    specific (node) ID over the more general (campaign) node.

    TODO: future work on this API may support multiple objects per invocation,
    additional lookup (e.g., by name) options, etc.

    Notes
    -----
    This API does not perform the work of processing the campaign or node;
    it performs the work of the daemon scheduling that work to be done, i.e.,
    by creating Task records. These Task records are still collected and acted
    upon by the daemon, so using this API is not a replacement for a Daemon.
    """
    if (request_id := correlation_id.get()) is None:
        raise HTTPException(status_code=500, detail="Cannot process resource without a X-Request-Id")
    match target:
        case ProcessTarget() if target.node_id is not None:
            # TODO when the RPC targets a Node, it should disallow the
            # operation if the associated campaign is not paused.
            node = await fetch_by_id(session, Node, target.node_id)
            campaign_id = node.namespace
            if node.status.is_terminal_script():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Node in a terminal state may not be processed.",
                )
            campaign_graph = await assemble_campaign_graph(session, campaign_id)
            # ensure the target node is "processable".
            processable_nodes = await to_thread.run_sync(processable_graph_nodes, campaign_graph)
            if node not in processable_nodes:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Node is not processable in the current campaign graph state.",
                )
            await daemon_process_node(session, node, request_id)
        case ProcessTarget() if target.campaign_id is not None:
            campaign = await fetch_by_id(session, Campaign, target.campaign_id)
            campaign_id = campaign.id
            if campaign.status not in [StatusEnum.waiting, StatusEnum.ready, StatusEnum.paused]:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Campaign must be in either a waiting, ready or paused state to be processed.",
                )
            await daemon_consider_campaign(session, campaign.id, request_id)
        case _:
            raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented.")

    await session.commit()

    response.headers["StatusUpdate"] = (
        f"""{request.url_for("read_campaign_activity_log", campaign_name=campaign_id)}"""
        f"""?request-id={request_id}"""
    ).strip()
