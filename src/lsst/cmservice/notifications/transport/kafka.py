import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from sqlalchemy.exc import NoResultFound

from lsst.cmservice.models.db.campaigns import Node
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import NotificationLabelEnum
from lsst.cmservice.models.lib.kafka.models import KafkaNotification
from lsst.cmservice.models.lib.kafka.producer import get_producer
from lsst.cmservice.models.lib.logging import LOGGER

from ...config import config
from ...db.session import db_session_dependency
from .abc import ActivityLog, NotificationPayload, NotificationTransport

logger = LOGGER.bind(module=__name__)


class KafkaTransport(NotificationTransport):
    """Notification transport for Kafka messages."""

    secret: Mapping  # pyright: ignore[reportRedeclaration]
    __kind__ = NotificationLabelEnum.kafka

    def notify(self, message: bytes | dict) -> None:
        """Sends a notification message."""

        data = message if isinstance(message, bytes) else json.dumps(message).encode()
        with get_producer(self.secret) as producer:
            producer.produce(data)

    async def anotify(self, message: bytes | dict) -> None:
        """Sends a notification message asynchronously."""

        raise NotImplementedError("Only synchronous notifications are supported")

    def build_message(self, node: Node, activity_log: ActivityLog) -> bytes:
        """Build a specific message payload, serialize it, and return it as
        bytes.
        """

        message_bytes = (
            KafkaNotification(
                node_name=node.name,
                node_url=f"{config.asgi.fqdn}/gui/node/{node.id}",
                campaign_name=node.campaign.name,
                campaign_url=f"{config.asgi.fqdn}/gui/campaign/{node.namespace}",
                from_status=activity_log.from_status,
                to_status=activity_log.to_status,
            )
            .model_dump_json()
            .encode()
        )
        return message_bytes

    async def deliver(self, payload: NotificationPayload) -> None:
        """Deliver a Kafka notification based on the payload delivered by the
        notification handler.
        """

        if TYPE_CHECKING:
            assert db_session_dependency.sessionmaker is not None
            assert config.notifications.fernet is not None

        # get the log AND the notification label from the database
        async with db_session_dependency.sessionmaker() as session:
            try:
                activity_log = await session.get_one(ActivityLog, payload.id)
                node: Node = await activity_log.awaitable_attrs.subject
                notification_label = await session.get(NotificationLabel, payload.label)
            except NoResultFound:
                logger.error(
                    "Notification subsystem did not find an activity log or "
                    "notification label when one was specified",
                    payload=payload,
                )
                return None

        # discover the kafka configuration from label.secret or use default
        self.secret: Mapping = {}
        if notification_label is None or payload.label == "default":
            notification_filters = self.default_filters
        else:
            raw_secret = config.notifications.fernet.decrypt(notification_label.secret)
            self.secret = json.loads(raw_secret)
            notification_filters = notification_label.configuration.get("filters", self.default_filters)

        if not await self.check_notification_filter(notification_filters, activity_log):
            return None

        message = self.build_message(node, activity_log)

        # dispatch the notification with notify
        self.notify(message)
