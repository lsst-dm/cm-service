"""Background task implementations for FSM-related operations performed via
API routes.
"""

import pickle

from ..common.enums import StatusEnum
from ..common.logging import LOGGER
from ..db.campaigns_v2 import Campaign, Node
from .campaign import CampaignMachine
from .node import NodeMachine

logger = LOGGER.bind(module=__name__)


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
        case (StatusEnum.waiting, StatusEnum.running):
            trigger = "start"
        case (StatusEnum.running, StatusEnum.paused):
            trigger = "pause"
        case (StatusEnum.paused, StatusEnum.running):
            trigger = "resume"
        case (_, StatusEnum.rejected):
            trigger = "reject"
        case (_, StatusEnum.accepted):
            trigger = "finish"
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

    # We require a pickled machine for this operation.
    node_machine: NodeMachine = (pickle.loads(node.fsm.state)).model
    node_machine.db_model = node

    trigger: str
    match (node.status, desired_state):
        case (StatusEnum.failed, StatusEnum.ready):
            trigger = "restart" if force else "retry"
        case (StatusEnum.failed, StatusEnum.waiting):
            trigger = "reset"
        case (StatusEnum.running, StatusEnum.paused):
            trigger = "pause"
        case (StatusEnum.paused, StatusEnum.running):
            trigger = "resume"
        case (_, StatusEnum.rejected):
            trigger = "reject"
        case (_, StatusEnum.accepted):
            trigger = "finish"
        case _:
            logger.warning(
                "Invalid node transition requested",
                id=str(node.id),
                source=node.status,
                dest=desired_state,
            )
            return None

    # If the requested trigger is valid, perform the action
    # NOTE we include the request_id for every callback we may invoke
    if await getattr(node_machine, f"may_{trigger}")(request_id=request_id):
        await node_machine.trigger(trigger, request_id=request_id, force=force)
