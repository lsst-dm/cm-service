"""Module for implementing notification functions through third-party message
systems.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import httpx

from ..config import config
from ..parsing.string import parse_element_fullname
from .enums import StatusEnum
from .logging import LOGGER

if TYPE_CHECKING:
    from ..db import Campaign, Job, Script

logger = LOGGER.bind(module=__name__)


SLACK_HEADER_SECTION = {
    StatusEnum.blocked: {
        "emoji": "ice_cube",
        "text": "One or more WMS Jobs are BLOCKED",
    },
    StatusEnum.failed: {
        "emoji": "dumpster-fire",
        "text": "One or more Campaign Nodes have FAILED",
    },
    StatusEnum.reviewable: {
        "emoji": "interrobang",
        "text": "One or more Campaign Nodes may require REVIEW",
    },
    StatusEnum.accepted: {
        "emoji": "100",
        "text": "A Campaign or Node is SUCCESSFUL",
    },
    StatusEnum.running: {
        "emoji": "tada",
        "text": "A Campaign has started RUNNING",
    },
    StatusEnum.rejected: {
        "emoji": "thumbsdown",
        "text": "A Campaign has been REJECTED",
    },
}


@asynccontextmanager
async def http_async_client(*, verify_host: bool = True) -> AsyncGenerator[httpx.AsyncClient]:
    """Generate a client session for http API operations."""
    transport = httpx.AsyncHTTPTransport(
        verify=verify_host,
        retries=3,
    )
    async with httpx.AsyncClient(transport=transport) as session:
        yield session


class Notification(ABC):
    @abstractmethod
    def notify(self, message: bytes | dict) -> None:
        """Sends a notification message."""
        ...

    @abstractmethod
    async def anotify(self, message: bytes | dict) -> None:
        """Sends a notification message asynchronously."""
        ...


class SlackNotification(Notification):
    headers: httpx.Headers = httpx.Headers({"Content-type": "application/json"})

    def notify(self, message: bytes | dict) -> None:
        raise NotImplementedError("Only asynchronous notifications are supported")

    async def anotify(self, message: bytes | dict) -> None:
        """Sends a Slack notification message asynchronously."""

        if config.notifications.slack_webhook_url is None:
            logger.warning("Cannot produce Slack notification without a webhook url set.")
            return None

        data = dict(text=message) if isinstance(message, bytes) else message

        async with http_async_client() as asession:
            try:
                response = await asession.post(
                    url=config.notifications.slack_webhook_url,
                    json=data,
                    headers=self.headers,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Unable to send Slack Notification",
                    http_status=e.response.status_code,
                    message=e.response.reason_phrase,
                )

        return None

    def build_message(self, status: StatusEnum, detail_text: str) -> dict | None:
        """Construct a Slack Block Kit message

        Raises
        ------
        KeyError
            If status is not valid for notification, i.e., it is not a terminal
            status.
        """

        try:
            use_header = SLACK_HEADER_SECTION[status]
        except KeyError:
            return None

        message = {
            "text": use_header["text"],
            "blocks": [
                # rich text header
                {
                    "type": "rich_text",
                    "elements": [
                        {
                            "type": "rich_text_section",
                            "elements": [
                                {"type": "emoji", "name": use_header["emoji"]},
                                {"type": "text", "text": use_header["text"]},
                            ],
                        }
                    ],
                },
                {"type": "divider"},
                # detail section
                {"type": "section", "text": {"type": "mrkdwn", "text": detail_text}},
                {"type": "divider"},
                # TODO footer
            ],
        }
        return message


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
