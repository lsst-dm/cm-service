"""Helpers for driving cm-web pages as a simulated NiceGUI user."""

import asyncio
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from typing import Any, Self

from nicegui import storage, ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction


def campaign_card(user: User, campaign_name: str) -> ui.card:
    """Find the overview card for a campaign by way of its name chip."""
    element: ui.element | None = user.find(kind=ui.chip, content=campaign_name).elements.pop()
    while element is not None and not isinstance(element, ui.card):
        element = element.parent_slot.parent if element.parent_slot else None
    assert element is not None, f"No card found for campaign {campaign_name}"
    return element


@contextmanager
def acting_as(user: User) -> Generator[None]:
    """Attribute interactions to the user's own browser session.

    In a running application, an event handler is called with the request of
    the page on which it was created, and NiceGUI's user storage is resolved
    from that request's session. The simulated user's interactions instead
    inherit the request of whichever user most recently opened a page, which
    would mix up the user storage of concurrently simulated users.
    """
    assert user.client is not None
    token = storage.request_contextvar.set(user.client.request)
    try:
        yield
    finally:
        storage.request_contextvar.reset(token)


def click(user: User, element: ui.element) -> None:
    """Click a specific element as the user."""
    with acting_as(user):
        UserInteraction(user, {element}, None).click()


def click_card_button[T: ui.button](user: User, campaign_name: str, kind: type[T]) -> None:
    """Click a button of the given kind on a campaign's overview card."""
    card = campaign_card(user, campaign_name)
    click(user, next(e for e in card.descendants() if isinstance(e, kind)))


async def open_drawer(user: User) -> None:
    """Open the page's right-hand drawer with the header's menu button."""
    await user.should_see(kind=ui.button, content="menu")
    with acting_as(user):
        user.find(kind=ui.button, content="menu").click()
    drawer = user.find(kind=ui.right_drawer).elements.pop()
    # the drawer's value is bound to the page and updated asynchronously
    for _ in range(20):
        if drawer.value:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("The drawer did not open")


def choose(user: User, label: str, *options: str) -> None:
    """Toggle options of a drawer select element as the user, by opening its
    popup, clicking each option, and closing it.
    """
    with acting_as(user), user.scope(kind=ui.right_drawer):
        user.find(kind=ui.select, content=label).click()
        for option in options:
            user.find(option).click()
        user.find(kind=ui.select, content=label).click()


def toggle(user: User, label: str) -> None:
    """Toggle a drawer switch as the user."""
    with acting_as(user), user.scope(kind=ui.right_drawer):
        user.find(kind=ui.switch, content=label).click()


def trigger(user: User, element: ui.element, event: str, args: Any = None) -> None:
    """Trigger an event on a specific element as the user, as the browser
    would emit it.
    """
    with acting_as(user):
        UserInteraction(user, {element}, None).trigger(event, args)


async def wait_for_navigation(user: User, path: str) -> None:
    """Wait for the user to navigate to a path, which simulated navigation does
    in a background task.
    """
    for _ in range(50):
        if user.back_history and user.back_history[-1] == path:
            return
        await asyncio.sleep(0.05)
    msg = f"The user did not navigate to {path}"
    raise AssertionError(msg)


async def follow_link(user: User, link: ui.link) -> None:
    """Click a link as the user and wait for the linked page to open."""
    target = link.props["href"]
    click(user, link)
    await wait_for_navigation(user, target)


def node_cards(user: User) -> dict[str, ui.card]:
    """The node cards on the page, by node name. A node card is a card linking
    to a node detail page.
    """
    cards = {}
    for card in user.find(kind=ui.card).elements:
        descendants = list(card.descendants())
        if any(isinstance(e, ui.link) and e.props["href"].startswith("/node/") for e in descendants):
            name = next(e.text for e in descendants if type(e) is ui.label)
            cards[name] = card
    return cards


async def eventually[T](get: Callable[[], T], predicate: Callable[[T], bool]) -> T:
    """Poll for a value until it satisfies the predicate, failing with a
    `TimeoutError` after five seconds.
    """
    async with asyncio.timeout(5.0):
        # the application offers no event to wait on, so the value is polled
        while not predicate(value := get()):  # noqa: ASYNC110
            await asyncio.sleep(0.05)
    return value


def campaign_switch(user: User) -> ui.switch:
    """The campaign's run/pause switch on the status gauge card."""
    return user.find(kind=ui.switch).elements.pop()


def notifications(user: User) -> list[ui.notification]:
    assert user.client is not None
    return [e for e in user.client.layout.descendants() if isinstance(e, ui.notification)]


async def open_campaign(user: User, campaign: dict) -> None:
    await user.open(f"/campaign/{campaign['id']}")
    await user.should_see("Campaign Graph", retries=20)


async def open_node(user: User, node: dict) -> None:
    await user.open(f"/node/{node['id']}")
    await user.should_see(kind=ui.timeline_entry, retries=20)


def timeline(user: User) -> list[str]:
    """The titles of the node timeline entries, newest first."""
    return [e.props["title"] for e in sorted(user.find(kind=ui.timeline_entry).elements, key=lambda e: e.id)]


def step_forward_chip(user: User) -> ui.chip:
    return next(c for c in user.find(kind=ui.chip).elements if c.props.get("icon") == "fast_forward")


async def open_recovery_dialog(user: User, node: dict) -> ui.dialog:
    """Open a failed node's detail page and click its "recover" chip, which
    opens the node recovery dialog.
    """
    await user.open(f"/node/{node['id']}")
    await user.should_see(kind=ui.chip, content="recover", retries=20)
    click(user, user.find(kind=ui.chip, content="recover").elements.pop())
    return (await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1))[0]


def open_dialogs(user: User) -> list[ui.dialog]:
    assert user.client is not None
    return [e for e in user.client.layout.descendants() if isinstance(e, ui.dialog) and e.value]


async def choose_recovery_action(user: User, node: dict, action: str) -> ui.notification:
    """Open a failed node's recovery dialog, choose a recovery action and
    confirm it, and return the notification of the action's progress.
    """
    dialog = await open_recovery_dialog(user, node)
    click(user, next(e for e in dialog.descendants() if isinstance(e, ui.chip) and e.text == action))
    await user.should_see(kind=ui.button, content="Yes")
    click(user, user.find(kind=ui.button, content="Yes").elements.pop())
    return (await eventually(lambda: notifications(user), lambda n: len(n) == 1))[0]


class FakeCanvas:
    """A stand-in for the graph canvas of the campaign editor pages, a
    JavaScript component that the simulated user cannot see or operate.

    The fake holds a graph of Svelte Flow nodes and edges, as the component
    does. Like the component, it answers the page's "canvasExport" event with
    a "canvasExported" event carrying the graph, and clicking one of its step
    nodes sends an "edit" event with the node's id and name.
    """

    EXPORT = re.compile(r'.*new CustomEvent\("canvasExport"\).*', re.DOTALL)

    def __init__(self, user: User, nodes: list[dict], edges: list[dict]) -> None:
        self.user = user
        self.nodes = nodes
        self.edges = edges
        self.exports = 0
        user.javascript_rules[self.EXPORT] = self.export

    @classmethod
    def with_steps(cls, user: User, *step_names: str) -> Self:
        """A canvas with a linear graph of new steps between START and END."""
        nodes = [
            {"id": f"n{i}", "type": "step", "data": {"name": name}, "position": {"x": 0, "y": 0}}
            for i, name in enumerate(step_names, start=1)
        ]
        nodes = [
            {"id": "START.1", "type": "start", "data": {"name": "START"}, "position": {"x": 0, "y": 0}},
            *nodes,
            {"id": "END.1", "type": "end", "data": {"name": "END"}, "position": {"x": 0, "y": 0}},
        ]
        edges = [
            {"id": f"e{i}", "source": source["id"], "target": target["id"]}
            for i, (source, target) in enumerate(zip(nodes, nodes[1:]), start=1)
        ]
        return cls(user, nodes, edges)

    def export(self, match: re.Match) -> None:
        """Answer the page's request to export the graph."""
        self.exports += 1
        assert self.user.client is not None
        graph = {"nodes": self.nodes, "edges": self.edges}
        trigger(self.user, self.user.client.layout, "canvasExported", {"data": graph})

    def click_node(self, node_id: str) -> None:
        """Click a step node, which asks the page to edit it."""
        node = next(n for n in self.nodes if n["id"] == node_id)
        assert self.user.client is not None
        trigger(self.user, self.user.client.layout, "edit", [node_id, node["data"]["name"]])
