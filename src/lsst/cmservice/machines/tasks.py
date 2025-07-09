"""Background task implementations for FSM-related operations performed via
API routes.
"""

from typing import TYPE_CHECKING
from uuid import UUID, uuid5

from sqlmodel import select

from ..common.enums import StatusEnum
from ..common.graph import graph_from_edge_list_v2, validate_graph
from ..common.logging import LOGGER
from ..db.campaigns_v2 import Campaign, Edge
from ..db.session import db_session_dependency
from .campaign import CampaignMachine

logger = LOGGER.bind(module=__name__)


async def change_campaign_state_fsm(campaign: Campaign, desired_state: StatusEnum, request_id: UUID) -> None:
    """A Background Task to affect a state change in a Campaign, using an
    FSM by triggering based on one of a handful of possible user-initiated
    state changes, as by PATCHing a campaign using the REST API.
    """

    logger.info(
        "Updating campaign state",
        campaign=str(campaign.id),
        request_id=str(request_id),
        dest=desired_state.name,
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
        case _:
            logger.warning(
                "Invalid campaign transition requested",
                id=str(campaign.id),
                source=campaign.status,
                dest=desired_state,
            )
            return None

    await campaign_machine.trigger(trigger, request_id=str(request_id))


async def change_campaign_state(campaign_id: UUID, desired_state: StatusEnum) -> None:
    """A Background Task to affect a state change in a Campaign, not using an
    FSM but by switching behavior on one of a handful of possible user-init-
    iated state changes, as by PATCHing a campaign using the REST API.
    """
    if TYPE_CHECKING:
        assert db_session_dependency.sessionmaker is not None

    async with db_session_dependency.sessionmaker() as session:
        # get the campaign instance from the db
        campaign = await session.get_one(Campaign, campaign_id)

        # TODO send notifications when appropriate
        match desired_state:
            case StatusEnum.running:
                if campaign.status in [StatusEnum.waiting, StatusEnum.paused]:
                    edges = await session.exec(select(Edge).where(Edge.namespace == campaign_id))
                    graph = await graph_from_edge_list_v2(edges.all(), session)
                    source = uuid5(campaign_id, "START.1")
                    sink = uuid5(campaign_id, "END.1")
                    if validate_graph(graph, source, sink):
                        campaign.status = desired_state
                    else:
                        logger.warning("Invalid campaign graph, cannot begin running", id=str(campaign_id))
                else:
                    pass
            case StatusEnum.paused:
                # Noop if the campaign is already paused; this will not mark
                # the session instance as dirty
                campaign.status = desired_state
            case _:
                logger.warning(
                    "Invalid state requested for campaign", id=str(campaign_id), state=desired_state.name
                )
                pass

        await session.commit()
