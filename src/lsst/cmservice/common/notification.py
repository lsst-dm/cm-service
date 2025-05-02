"""Module for implementing notification functions through third-party message
systems.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import TYPE_CHECKING, TypedDict

import httpx

from ..config import config
from .enums import StatusEnum
from .logging import LOGGER

if TYPE_CHECKING:
    from ..db import Campaign, Job

logger = LOGGER.bind(module=__name__)


class RichTextSection(TypedDict):
    type: str
    elements: list


SLACK_NOTIFICATION = {
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "plain_text",
                "emoji": True,
                "text": "A Campaign Job has entered a terminal state:",
            },
        },
        {"type": "divider"},
    ]
}


SLACK_JOB_BLOCKED_SECTION: RichTextSection = {
    "type": "rich_text_section",
    "elements": [
        {"type": "emoji", "name": "ice_cube"},
        {"type": "text", "text": "One or more WMS Jobs are BLOCKED"},
    ],
}
"""A template message section for notifying a CM Job has been blocked."""


SLACK_JOB_FAILED_SECTION: RichTextSection = {
    "type": "rich_text_section",
    "elements": [
        {"type": "emoji", "name": "dumpster-fire"},
        {"type": "text", "text": "One or more WMS Jobs are FAILED"},
    ],
}
"""A template message section for notifying a CM Job has failed."""


SLACK_JOB_REVIEWABLE_SECTION: RichTextSection = {
    "type": "rich_text_section",
    "elements": [
        {"type": "emoji", "name": "interrobang"},
        {"type": "text", "text": "One or more WMS Jobs may require REVIEW"},
    ],
}
"""A template message section for notifying a CM Job has failed."""

SLACK_JOB_DONE_SECTION: RichTextSection = {
    "type": "rich_text_section",
    "elements": [
        {"type": "emoji", "name": "100"},
        {"type": "text", "text": "The campaign or job is SUCCESSFUL"},
    ],
}
"""A template message section for notifying a CM Job has finished."""


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


async def send_notification(
    for_status: StatusEnum, for_campaign: "Campaign", for_job: "Job | None" = None
) -> None:
    """Sends a notification message."""

    # TODO only Slack webhooks are supported at the moment, but if additional
    #      notifications channels are added, this function can address each
    #      one in turn.
    # This function is a no-op if there are no notification channels configured
    if not any([config.notifications.slack_webhook_url]):
        return None

    message = deepcopy(SLACK_NOTIFICATION)

    campaign_name = for_campaign.fullname

    # a section for the element details
    # TODO construct a link to the appropriate web_app area for the referenced
    #      elements
    detail_text = f"*{campaign_name}*"
    if for_job is not None:
        detail_text += f"\n*<{for_job.fullname}>*"
    message["blocks"].append(
        {"type": "section", "text": {"type": "mrkdwn", "text": detail_text}},
    )

    rich_text: RichTextSection = {"type": "rich_text", "elements": []}

    match for_status:
        case StatusEnum.blocked:
            rich_text["elements"].append(SLACK_JOB_BLOCKED_SECTION)
        case StatusEnum.failed:
            rich_text["elements"].append(SLACK_JOB_FAILED_SECTION)
        case StatusEnum.accepted:
            rich_text["elements"].append(SLACK_JOB_DONE_SECTION)
        case StatusEnum.reviewable:
            rich_text["elements"].append(SLACK_JOB_REVIEWABLE_SECTION)
        case _:
            # Only notify on terminal states
            return None

    message["blocks"].append(rich_text)
    return await SlackNotification().anotify(message)
