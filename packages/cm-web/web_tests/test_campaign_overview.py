"""Tests for the campaign overview (landing) page."""

from collections.abc import Callable

import pytest
from nicegui import ui
from nicegui.testing.user import User

from lsst.cmservice.web.components.button import FavoriteButton, TrashButton

from .conftest import FakeCMService
from .interactions import acting_as, campaign_card, choose, click_card_button, open_drawer, toggle

WEYLAND = {"nostromo", "narcissus", "covenant"}
"""Fixture campaigns owned by weyland."""

YUTANI = {"sulaco", "auriga"}
"""Fixture campaigns owned by yutani."""

EVERYONE = WEYLAND | YUTANI


async def should_see_campaigns(user: User, visible: set[str]) -> None:
    """Assert that exactly the given fixture campaigns are visible."""
    for name in sorted(EVERYONE):
        if name in visible:
            await user.should_see(name)
        else:
            await user.should_not_see(name)


async def test_overview_shows_fixture_campaigns(
    user: User, cm_api: FakeCMService, fixture_campaigns: list[dict]
) -> None:
    await user.open("/")
    await user.should_see("Campaign Overview")

    for campaign in fixture_campaigns:
        await user.should_see(campaign["name"])
        await user.should_see(campaign["owner"])
        await user.should_see(campaign["id"])

        # the campaign card's state switch is labeled with the campaign status,
        # is on only for a running campaign, and is disabled for a campaign in
        # a terminal state.
        switch = user.find(kind=ui.switch, content=campaign["status"]).elements.pop()
        assert switch.value is (campaign["status"] == "running")
        assert switch.enabled is (campaign["status"] not in ("accepted", "failed", "rejected"))

    assert cm_api.router.routes["campaign_summary"].call_count == len(fixture_campaigns)


async def test_overview_node_summary(user: User, fixture_campaigns: list[dict]) -> None:
    """The nostromo campaign card summarizes its nodes by status, including the
    campaign's START and END nodes.
    """
    await user.open("/")
    await user.should_see("nostromo")
    card = campaign_card(user, "nostromo")

    # node summary chips show a count and have the node status as a tooltip,
    # which is a sibling element targeting the chip.
    descendants = list(card.descendants())
    tooltips = {e.props["target"]: e.text for e in descendants if isinstance(e, ui.tooltip)}
    node_summary = {
        tooltips[f"#{e.html_id}"]: e.text
        for e in descendants
        if isinstance(e, ui.chip) and isinstance(e.text, int)
    }
    assert node_summary == {"accepted": 1, "running": 1, "waiting": 3}


# -- drawer filters --------------------------------------------------------- #


async def test_anonymous_user_sees_all_owners(user: User, fixture_campaigns: list[dict]) -> None:
    """Without a username there is no default owner filter."""
    await user.open("/")
    await should_see_campaigns(user, EVERYONE)


@pytest.mark.parametrize(("username", "owned"), [("weyland", WEYLAND), ("yutani", YUTANI)])
async def test_owner_filter_defaults_to_user(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict], username: str, owned: set[str]
) -> None:
    """A user initially sees only their own campaigns, and sees every campaign
    when they deselect themselves from the owner filter.
    """
    user = create_user(username)
    await user.open("/")
    await should_see_campaigns(user, owned)

    await open_drawer(user)
    choose(user, "Filter by Owner", username)
    await should_see_campaigns(user, EVERYONE)


async def test_owner_filter_is_remembered(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict]
) -> None:
    """An owner added to the filter is remembered across page loads."""
    weyland = create_user("weyland")
    await weyland.open("/")
    await open_drawer(weyland)
    # "yutani" is not one of the select's options; a user adds it by typing a
    # new value, which the simulated user cannot do, so the value is set.
    with acting_as(weyland), weyland.scope(kind=ui.right_drawer):
        weyland.find(kind=ui.select, content="Filter by Owner").elements.pop().set_value(
            ["weyland", "yutani"]
        )
    await should_see_campaigns(weyland, EVERYONE)

    await weyland.open("/")
    await should_see_campaigns(weyland, EVERYONE)


@pytest.mark.parametrize(
    ("username", "statuses", "visible"),
    [
        (None, ["running"], {"nostromo", "covenant"}),
        (None, ["paused"], {"sulaco", "auriga"}),
        (None, ["accepted", "running"], {"narcissus", "nostromo", "covenant"}),
        # campaigns with failed nodes are not themselves failed
        (None, ["failed"], set()),
        (None, ["rejected"], set()),
        ("weyland", ["paused", "running"], {"nostromo", "covenant"}),
        ("yutani", ["paused", "running"], {"sulaco", "auriga"}),
    ],
)
async def test_status_filter(
    create_user: Callable[[str | None], User],
    fixture_campaigns: list[dict],
    username: str | None,
    statuses: list[str],
    visible: set[str],
) -> None:
    """The status filter shows campaigns with any of the selected statuses,
    in combination with the owner filter.
    """
    user = create_user(username)
    await user.open("/")
    await open_drawer(user)
    choose(user, "Filter by Status", *statuses)
    await should_see_campaigns(user, visible)

    # deselecting the statuses removes the status filter
    choose(user, "Filter by Status", *statuses)
    await should_see_campaigns(
        user, EVERYONE if username is None else WEYLAND if username == "weyland" else YUTANI
    )


async def test_favorites_filter(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict]
) -> None:
    """Each user's favorites filter shows only the campaigns that user has
    marked as a favorite, and stays active across page loads.
    """
    weyland = create_user("weyland")
    yutani = create_user("yutani")

    for user, favorite in ((weyland, "nostromo"), (yutani, "sulaco")):
        await user.open("/")
        await user.should_see(favorite)
        click_card_button(user, favorite, FavoriteButton)

    for user, username, favorite in ((weyland, "weyland", "nostromo"), (yutani, "yutani", "sulaco")):
        await open_drawer(user)
        choose(user, "Filter by Owner", username)
        await should_see_campaigns(user, EVERYONE)
        toggle(user, "Favorites")
        await should_see_campaigns(user, {favorite})

    # the favorites filter and the favorites are remembered
    await weyland.open("/")
    await should_see_campaigns(weyland, {"nostromo"})


async def test_hidden_campaigns(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict]
) -> None:
    """A campaign hidden by one user is hidden only for that user, stays
    hidden across page loads, and is shown with the "Show Hidden" switch.
    """
    weyland = create_user("weyland")
    yutani = create_user("yutani")

    # NOTE the page is loaded once beforehand so this is not weyland's first
    # visit; see `test_show_hidden_is_off_on_first_visit`.
    await weyland.open("/")
    await weyland.open("/")
    await weyland.should_see("narcissus")
    click_card_button(weyland, "narcissus", TrashButton)
    await should_see_campaigns(weyland, WEYLAND - {"narcissus"})

    await yutani.open("/")
    await open_drawer(yutani)
    choose(yutani, "Filter by Owner", "yutani")
    await should_see_campaigns(yutani, EVERYONE)

    await weyland.open("/")
    await should_see_campaigns(weyland, WEYLAND - {"narcissus"})
    await open_drawer(weyland)
    toggle(weyland, "Show Hidden")
    await should_see_campaigns(weyland, WEYLAND)

    # un-hiding the campaign shows it without the "Show Hidden" switch
    click_card_button(weyland, "narcissus", TrashButton)
    toggle(weyland, "Show Hidden")
    await should_see_campaigns(weyland, WEYLAND)
    await weyland.open("/")
    await should_see_campaigns(weyland, WEYLAND)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The drawer, including the Show Hidden switch, is created in CMPage.__init__ before "
        "CampaignOverviewPage.setup() adds the default 'ignored' filter, so a new user starts "
        "with Show Hidden on."
    ),
)
async def test_show_hidden_is_off_on_first_visit(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict]
) -> None:
    weyland = create_user("weyland")
    await weyland.open("/")
    await weyland.should_see("Show Hidden")
    with weyland.scope(kind=ui.right_drawer):
        assert weyland.find(kind=ui.switch, content="Show Hidden").elements.pop().value is False


@pytest.mark.xfail(
    strict=True,
    reason=(
        "User preferences are kept in NiceGUI user storage, which is keyed by the browser session "
        "rather than by the X-Auth-Request-User identity, so they are shared by everyone using "
        "the same browser."
    ),
)
async def test_favorites_belong_to_the_user(
    create_user: Callable[[str | None], User], fixture_campaigns: list[dict]
) -> None:
    """Favorites marked by one user are not favorites of a different user who
    later uses the same browser.
    """
    browser = create_user("weyland")
    await browser.open("/")
    await browser.should_see("nostromo")
    click_card_button(browser, "nostromo", FavoriteButton)

    browser.http_client.headers["X-Auth-Request-User"] = "yutani"
    await browser.open("/")
    await open_drawer(browser)
    choose(browser, "Filter by Owner", "yutani")
    toggle(browser, "Favorites")
    await should_see_campaigns(browser, set())
