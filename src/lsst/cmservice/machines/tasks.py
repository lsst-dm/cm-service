"""Background task implementations for FSM-related operations performed via
API routes.
"""

import pickle

from transitions.core import MachineError

from lsst.cmservice.models.db.campaigns import ActivityLog, Campaign, Node
from lsst.cmservice.models.enums import ManifestKind, StatusEnum
from lsst.cmservice.models.lib import timestamp

from ..common.logging import LOGGER
from ..db.session import db_session_dependency
from .campaign import CampaignMachine
from .node import NodeMachine, node_machine_factory

logger = LOGGER.bind(module=__name__)


async def record_refused_transition(node: Node, request_id: str, reason: str) -> None:
    """Record a completed activity log entry for a user-requested node state
    change that was refused, so that the requester, who is waiting for
    activity matching its request id, is informed of the refusal instead of
    waiting for an activity that never arrives.
    """
    if db_session_dependency.sessionmaker is None:
        logger.error("Cannot record refused transition without a database session", id=str(node.id))
        return
    async with db_session_dependency.sessionmaker() as session:
        session.add(
            ActivityLog(
                namespace=node.namespace,
                node=node.id,
                operator="daemon",
                from_status=node.status,
                to_status=node.status,
                detail={"error": reason},
                metadata_={"request_id": request_id},
                finished_at=timestamp.now_utc(),
                notification_labels=[],
            )
        )
        await session.commit()


async def change_campaign_state(
    campaign: Campaign, desired_state: StatusEnum, request_id: str, *, force: bool = False
) -> None:
    """A Background Task to affect a state change in a Campaign, using an
    FSM by triggering based on one of a handful of possible user-initiated
    state changes, as by PATCHing a campaign using the REST API.

    The ``force`` argument is meant to make the state change unconditional, but
    this is implementation-dependent within the FSM trigger callback.
    """

    logger.info(
        "Updating campaign state",
        campaign=str(campaign.id),
        request_id=request_id,
        dest=desired_state.name,
        force=force,
    )
    # Establish an FSM for the Campaign initialized to the current status
    campaign_machine = CampaignMachine(o=campaign, initial_state=campaign.status)

    trigger: str
    match (campaign.status, desired_state):
        # DEPRECATED: campaign waiting/start state/trigger
        case (StatusEnum.waiting, StatusEnum.running):
            trigger = "start"
        case (StatusEnum.running, StatusEnum.paused):
            trigger = "pause"
        case (StatusEnum.paused, StatusEnum.running):
            trigger = "resume"
        case (_, StatusEnum.rejected):
            trigger = "reject"
        case (_, StatusEnum.accepted):
            trigger = "force" if force else "finish"
        case _:
            logger.warning(
                "Invalid campaign transition requested",
                id=str(campaign.id),
                source=campaign.status,
                dest=desired_state,
            )
            return None

    await campaign_machine.trigger(trigger, request_id=request_id, force=force)


async def change_node_state(
    node: Node, desired_state: StatusEnum, request_id: str, *, force: bool = False
) -> None:
    """A Background Task to affect a state change in a Node, using an
    FSM by triggering based on one of a handful of possible user-initiated
    state changes, as by PATCHing a node using the REST API.

    The ``force`` argument is meant to make the state change unconditional, but
    this is implementation-dependent within the FSM trigger callback. The
    ``force`` argument may also be used to disambiguate between "soft" and
    "hard" transitions between the same states, such as "failed->ready" which
    may be performed as a soft "retry" or a hard "restart".
    """

    logger.info(
        "Updating node state",
        node=str(node.id),
        request_id=request_id,
        dest=desired_state.name,
        force=force,
    )

    if node.fsm is not None:
        node_machine: NodeMachine = (pickle.loads(node.fsm.state)).model
        node_machine.db_model = node
    elif node.status is StatusEnum.waiting:
        # create a new machine for the node
        node_machine = node_machine_factory(node.kind)(o=node, initial_state=node.status)
    else:
        logger.warning("Cannot change node state without a pickled machine", id=str(node.id))
        await record_refused_transition(
            node, request_id, "Cannot change node state without a state machine except from waiting"
        )
        return None

    trigger: str
    match (node.status, desired_state):
        case (StatusEnum.waiting, StatusEnum.ready):
            trigger = "prepare"
        case (StatusEnum.failed, StatusEnum.ready):
            trigger = "restart" if force else "retry"
        case (StatusEnum.failed, StatusEnum.waiting):
            trigger = "reset"
        case (StatusEnum.running, StatusEnum.paused):
            trigger = "pause"
        case (StatusEnum.paused, StatusEnum.running):
            trigger = "resume"
        case (StatusEnum.accepted, StatusEnum.rejected):
            trigger = "reject"
        case (current, StatusEnum.rejected) if (
            node.kind is ManifestKind.breakpoint and current.is_processable_script()
        ):
            # A breakpoint may be rejected before it is reached by the campaign
            # (waiting) or while it is holding the campaign (running)
            trigger = "reject"
        case (_, StatusEnum.accepted):
            trigger = "force" if force else "finish"
        case (_, StatusEnum.failed):
            trigger = "fail"
        case _:
            logger.warning(
                "Invalid node transition requested",
                id=str(node.id),
                source=node.status,
                dest=desired_state,
            )
            await record_refused_transition(
                node,
                request_id,
                f"A node cannot be changed from {node.status.name} to {desired_state.name}",
            )
            return None

    # NOTE we include the request_id for every callback we may invoke
    try:
        await node_machine.trigger(trigger, request_id=request_id, force=force)
    except MachineError:
        logger.warning("Node cannot perform requested transition", request_id=request_id)
        await record_refused_transition(
            node,
            request_id,
            f"A {node.kind.name} node cannot perform the '{trigger}' transition from {node.status.name}",
        )
