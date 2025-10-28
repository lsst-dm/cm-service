"""Background task implementations for FSM-related operations performed via
API routes.
"""

from ..common.enums import StatusEnum
from ..common.logging import LOGGER
from ..db.campaigns_v2 import Campaign
from .campaign import CampaignMachine

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
