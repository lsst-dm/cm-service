from asyncio import sleep

from nicegui import ui

from ..lib.client_factory import CLIENT_FACTORY


async def wait_for_activity_to_complete(url: str, n: ui.notification) -> None:
    """Given a URL to an activity log API, wait for the activity to report a
    complete state.
    """
    async with CLIENT_FACTORY.aclient() as client:
        while True:
            r = await client.get(url)
            if not len(r.json()):
                await sleep(5.0)
            else:
                break
        activity = r.json()[0]
        if (error := activity.get("detail", {}).get("error")) is not None:
            n.type = "negative"
            n.message = error
        else:
            n.type = "positive"
            n.message = "Node Recovered"
        n.spinner = False
        n.timeout = 5.0
    return None
