"""Module for implementing notification functions through third-party message
systems.

.. deprecated:: 1.0.0
    'lsst.cmservice.common.notification` is deprecated in favor of transport-
    based `lsst.cmservice.notifications`
"""

from typing import TYPE_CHECKING

from lsst.cmservice.models.enums import StatusEnum
from lsst.cmservice.models.lib.logging import LOGGER

from ..config import config
from ..notifications.transport.slack import SlackNotification
from ..parsing.string import parse_element_fullname

if TYPE_CHECKING:
    from ..db import Campaign, Job, Script

logger = LOGGER.bind(module=__name__)


async def send_notification(
    for_status: StatusEnum,
    for_campaign: "Campaign",
    for_job: "Job | Script | None" = None,
    detail: str | None = None,
) -> None:
    """Sends a notification message."""

    # TODO only Slack webhooks are supported at the moment, but if additional
    #      notifications channels are added, this function can address each
    #      one in turn.
    # This function is a no-op if there are no notification channels configured
    if not any([config.notifications.slack_webhook_url]):
        return None

    slack_notifier = SlackNotification()
    campaign_name = parse_element_fullname(for_campaign.fullname)
    campaign_link = f"{config.asgi.fqdn}{config.asgi.frontend_prefix}/campaign/{for_campaign.id}/steps"
    detail_text = f"<{campaign_link}|*{campaign_name.campaign}*>"

    if for_job is not None:
        detail_text += f"\n_{for_job.fullname}_"
    if detail is not None:
        detail_text += f"\n>{detail}"
    message = slack_notifier.build_message(
        status=for_status,
        detail_text=detail_text,
    )
    if message is not None:
        return await SlackNotification().anotify(message)
    else:
        return None
