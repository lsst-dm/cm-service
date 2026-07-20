import json
from typing import TYPE_CHECKING

import httpx
from sqlalchemy.exc import NoResultFound

from lsst.cmservice.models.db.campaigns import ActivityLog
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import NotificationLabelEnum, StatusEnum
from lsst.cmservice.models.lib.logging import LOGGER

from ...config import config
from ...db.session import db_session_dependency
from .abc import NotificationPayload, NotificationTransport

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
    StatusEnum.overdue: {
        "emjoji": "calendar",
        "text": "A Campaign is taking TOO LONG",
    },
}


class SlackNotification(NotificationTransport):
    __kind__ = NotificationLabelEnum.slack
    headers: httpx.Headers = httpx.Headers({"Content-type": "application/json"})
    slack_webhook_url: str | None = None

    def notify(self, message: bytes | dict) -> None:
        raise NotImplementedError("Only asynchronous notifications are supported")

    async def anotify(self, message: bytes | dict) -> None:
        """Sends a Slack notification message asynchronously."""

        if self.slack_webhook_url is None:
            logger.warning("Cannot produce Slack notification without a webhook url set.")
            return None

        data = dict(text=message) if isinstance(message, bytes) else message

        async with self.http_async_client() as asession:
            try:
                response = await asession.post(
                    url=self.slack_webhook_url,
                    json=data,
                    headers=self.headers,
                )
                response.raise_for_status()
            except httpx.ConnectError as e:
                logger.error(
                    "Unable to connect to Slack endpoint",
                    message=e,
                )
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Unable to send Slack Notification",
                    http_status=e.response.status_code,
                    message=e.response.reason_phrase,
                )

        return None

    def build_message(self, status: StatusEnum, detail_text: str) -> dict | None:
        """Construct a Slack Block Kit message"""

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

    async def deliver(self, payload: NotificationPayload) -> None:
        """Deliver a Slack notification based on the payload delivered by the
        notification handler.
        """
        if TYPE_CHECKING:
            assert db_session_dependency.sessionmaker is not None
            assert config.notifications.fernet is not None

        # get the log AND the notification label from the database
        async with db_session_dependency.sessionmaker() as session:
            try:
                activity_log = await session.get_one(ActivityLog, payload.id)
                notification_label = await session.get(NotificationLabel, payload.label)
            except NoResultFound:
                logger.error(
                    "Notification subsystem did not find an activity log or "
                    "notification label when one was specified",
                    payload=payload,
                )
                return None

        # TODO filter the log entry according to rules
        # (notification_label.configuration?)
        if activity_log.to_status not in SLACK_HEADER_SECTION:
            return None

        # TODO build a message from the log entry
        detail = json.dumps(activity_log.detail) or "Node transitioned"
        message = self.build_message(activity_log.to_status, detail)
        if message is None:
            return None

        # discover the slack webhook url from the label.secret or use default
        if notification_label is None:
            self.slack_webhook_url = config.notifications.slack_webhook_url
        else:
            self.slack_webhook_url = config.notifications.fernet.decrypt(notification_label.secret).decode()

        # dispatch the notification with anotify
        await self.anotify(message)
