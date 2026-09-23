import asyncio
from contextlib import AbstractContextManager, nullcontext
from urllib.parse import urlparse
from uuid import UUID, uuid4, uuid5

import pytest
from httpx2 import AsyncClient
from pytest_mock import MockerFixture
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.config import config
from lsst.cmservice.models.db.campaigns import ActivityLog, Node
from lsst.cmservice.models.db.notifications import NotificationLabel
from lsst.cmservice.models.enums import NotificationLabelEnum, StatusEnum

pytestmark = pytest.mark.asyncio(loop_scope="module")
"""All tests in this module will run in the same event loop."""


async def test_notification_label_routes(test_campaign_groups: str, aclient: AsyncClient) -> None:
    """Test the CRUD routes for a notification label"""
    plaintext = "http://hooks.mock.com/services/XXXXXXXX/XXXXXXXX/XXXXXXXX"
    r = await aclient.post(
        "/v2/notifications",
        json={
            "kind": "notification_label",
            "metadata": {
                "name": "slack-test",
                "kind": "slack",
            },
            "spec": {"plaintext": plaintext},
        },
    )
    assert r.is_success

    r = await aclient.get(r.headers["Self"])
    assert r.is_success
    label = r.json()
    assert label["secret"] != plaintext


@pytest.mark.parametrize(
    ("filter_value", "cm"),
    [
        (["*:*:accepted"], nullcontext()),
        (["step:running:accepted"], nullcontext()),
        (["*:running:*", "*:*:failed"], nullcontext()),
        (["*:*:failed"], pytest.raises(asyncio.TimeoutError)),
        (["group:running:accepted"], pytest.raises(asyncio.TimeoutError)),
        (["*:ready:*", "*:*:failed"], pytest.raises(asyncio.TimeoutError)),
    ],
    ids=["simple pass", "saturated pass", "compound pass", "simple fail", "saturated fail", "compound fail"],
)
async def test_slack_notifier_task(
    filter_value: list[str],
    cm: AbstractContextManager,
    mocker: MockerFixture,
    session: AsyncSession,
    test_campaign_groups: str,
    notifications_tg: None,
) -> None:
    """Test the generation of a Slack notification in response to an activity
    log entry added to the database.
    """
    label_name = str(uuid4())[-8:]
    assert config.notifications.fernet is not None
    # set sentinel for notification call
    notify_called = asyncio.Event()

    async def notify_side_effect(message: str | bytes) -> None:
        """set the sentinel event indicating this mock as been called"""
        notify_called.set()

    mocker.patch(
        "lsst.cmservice.notifications.transport.slack.SlackNotification.anotify",
        side_effect=notify_side_effect,
    )
    campaign_id = urlparse(url=test_campaign_groups).path.split("/")[-2:][0]
    node_id = uuid5(UUID(campaign_id), "lambert.1")

    node = await session.get_one(Node, node_id)

    # create a new notification label
    label = NotificationLabel(
        name=label_name,
        kind=NotificationLabelEnum.slack,
        configuration={"filters": filter_value},
        secret=config.notifications.fernet.encrypt(b"http://mockslack/asdfasdfasdf"),
    )
    session.add(label)
    await session.commit()

    # create a new activity log
    activity = ActivityLog(
        namespace=node.campaign.id,
        node=node.id,
        operator="test",
        from_status=StatusEnum.running,
        to_status=StatusEnum.accepted,
        detail={},
        metadata_={},
        notification_labels=[label_name],
    )
    session.add(activity)
    await session.commit()

    with cm:
        await asyncio.wait_for(notify_called.wait(), timeout=5.0)
