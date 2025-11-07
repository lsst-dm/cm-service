from asyncio import sleep

from nicegui import ui

from ..lib.client_factory import CLIENT_FACTORY
from ..settings import settings


async def wait_for_activity_to_complete(url: str, n: ui.notification) -> None:
    """Given a URL to an activity log API, wait for the activity to report a
    complete state.
    """
    time_budget = settings.timeout
    inter_request_wait_time = 5.0
    async with CLIENT_FACTORY.aclient() as client:
        while time_budget > 0:
            r = await client.get(url)
            if not len(r.json()):
                await sleep(inter_request_wait_time)
                time_budget -= inter_request_wait_time
            else:
                break
        activity = r.json()[0]
        if time_budget <= 0:
            n.type = "warning"
            n.message = "Timed out waiting for result"
        elif (error := activity.get("detail", {}).get("error")) is not None:
            n.type = "negative"
            n.message = error
        else:
            n.type = "positive"
            n.message = "Node Recovered"
        n.spinner = False
        n.timeout = 5.0
    return None
