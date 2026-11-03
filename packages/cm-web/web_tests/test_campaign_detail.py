"""Tests for the campaign detail page."""

import re

import pytest
from nicegui import ui
from nicegui.testing.user import User

from .conftest import STATUS_FILL_COLORS, FakeCMService
from .interactions import campaign_card, click, follow_link, node_cards, open_campaign, open_drawer, trigger

AURIGA_NODES = {"START", "call", "vriess", "END"}
"""The nodes of the auriga fixture campaign, all of which are waiting."""


def expansion(user: User, label: str) -> ui.expansion:
    return user.find(kind=ui.expansion, content=label).elements.pop()


def set_expanded(user: User, label: str, *, value: bool) -> ui.expansion:
    """Open or close an expansion as the user, as the browser reports it."""
    element = expansion(user, label)
    trigger(user, element, "update:modelValue", value)
    assert element.value is value
    return element


def manifest_names(manifests: ui.expansion) -> set[str]:
    """The names of the manifests on the manifest cards in an expansion."""
    return {
        e.text
        for card in manifests.descendants()
        if isinstance(card, ui.card)
        for e in card.descendants()
        if type(e) is ui.label
    }


@pytest.fixture
async def auriga(user: User, fixture_campaigns: list[dict]) -> dict:
    """Drills into the (paused, all-nodes-waiting) auriga campaign from the
    campaign overview page.
    """
    campaign = next(c for c in fixture_campaigns if c["name"] == "auriga")
    await user.open("/")
    await user.should_see("auriga")
    link = next(e for e in campaign_card(user, "auriga").descendants() if isinstance(e, ui.link))
    await follow_link(user, link)
    await user.should_see("Campaign Graph", retries=20)
    return campaign


async def test_drill_into_waiting_campaign(user: User, cm_api: FakeCMService, auriga: dict) -> None:
    assert user.back_history[-1] == f"/campaign/{auriga['id']}"
    await user.should_see(kind=ui.label, content="auriga")

    cards = node_cards(user)
    assert set(cards) == AURIGA_NODES
    for card in cards.values():
        assert "waiting" in {e.text for e in card.descendants() if isinstance(e, ui.chip)}

    # the fixture campaigns have no campaign manifests
    manifests = set_expanded(user, "Campaign Manifests", value=True)
    assert manifest_names(manifests) == set()
    assert cm_api.router.routes["campaign_manifests"].call_count == 1


async def test_campaign_manifests(user: User, cm_api: FakeCMService, fixture_campaigns: list[dict]) -> None:
    """The manifests expansion shows the campaign's own manifests, and not
    library manifests.
    """
    auriga = next(c for c in fixture_campaigns if c["name"] == "auriga")
    cm_api.add_manifest("butler", "muthur", namespace=auriga["id"], spec={"repo": "/repo/mock"})
    cm_api.add_manifest("wms", "htcondor", namespace=auriga["id"])
    cm_api.add_manifest("site", "lv426", default=True)

    await open_campaign(user, auriga)
    manifests = set_expanded(user, "Campaign Manifests", value=True)
    assert manifest_names(manifests) == {"muthur", "htcondor"}


async def test_expansions(user: User, fixture_campaigns: list[dict]) -> None:
    """The graph and manifest expansions are closed initially, open and close
    independently, and contain the graph and manifests respectively.

    The simulated user cannot see whether the browser renders the contents of
    a closed expansion, so this checks the expansion state and which elements
    belong to each expansion.
    """
    auriga = next(c for c in fixture_campaigns if c["name"] == "auriga")
    await open_campaign(user, auriga)

    graph, manifests = expansion(user, "Campaign Graph"), expansion(user, "Campaign Manifests")
    assert (graph.value, manifests.value) == (False, False)
    assert [type(e) for e in graph.descendants() if isinstance(e, ui.mermaid)] == [ui.mermaid]
    assert not any(isinstance(e, ui.mermaid) for e in manifests.descendants())
    assert not any(isinstance(e, ui.card) for e in graph.descendants())

    set_expanded(user, "Campaign Graph", value=True)
    assert (graph.value, manifests.value) == (True, False)
    set_expanded(user, "Campaign Manifests", value=True)
    assert (graph.value, manifests.value) == (True, True)
    set_expanded(user, "Campaign Graph", value=False)
    assert (graph.value, manifests.value) == (False, True)
    set_expanded(user, "Campaign Manifests", value=False)
    assert (graph.value, manifests.value) == (False, False)


@pytest.mark.parametrize("campaign_name", ["auriga", "nostromo", "sulaco", "narcissus", "covenant"])
async def test_graph_colors(
    user: User, cm_api: FakeCMService, fixture_campaigns: list[dict], campaign_name: str
) -> None:
    """The campaign graph diagram has a node for each campaign node, filled
    with the color for the node's status, and the campaign's edges.
    """
    campaign = next(c for c in fixture_campaigns if c["name"] == campaign_name)
    await open_campaign(user, campaign)
    graph = set_expanded(user, "Campaign Graph", value=True)
    mermaid = next(e for e in graph.descendants() if isinstance(e, ui.mermaid))

    nodes = [n for n in cm_api.nodes.values() if n["namespace"] == campaign["id"]]
    fills = dict(re.findall(r"^style (\S+) fill:(#[0-9a-f]{6})$", mermaid.content, re.MULTILINE))
    assert fills == {f"{n['name']}.{n['version']}": STATUS_FILL_COLORS[n["status"]] for n in nodes}

    def graph_name(node_id: str) -> str:
        return f"{cm_api.nodes[node_id]['name']}.{cm_api.nodes[node_id]['version']}"

    edges = set(re.findall(r"(\S+) --> (\S+);", mermaid.content))
    assert edges == {(graph_name(s), graph_name(t)) for s, t in cm_api.edges[campaign["id"]]}


async def test_expanded_step_graph(user: User, cm_api: FakeCMService, fixture_campaigns: list[dict]) -> None:
    """The covenant campaign's daniels step has been expanded into a group and
    collect subgraph ahead of its failed walter step.
    """
    covenant = next(c for c in fixture_campaigns if c["name"] == "covenant")
    await open_campaign(user, covenant)
    graph = set_expanded(user, "Campaign Graph", value=True)
    mermaid = next(e for e in graph.descendants() if isinstance(e, ui.mermaid))

    path = ["START", "daniels", "daniels_group_001", "daniels_collect_groups", "walter", "END"]
    edges = re.findall(r"(\S+) --> (\S+);", mermaid.content)
    assert sorted(edges) == sorted((f"{s}.1", f"{t}.1") for s, t in zip(path, path[1:]))

    cards = node_cards(user)
    assert set(cards) == set(path)
    statuses = {
        n["name"]: (n["kind"], n["status"]) for n in cm_api.nodes.values() if n["namespace"] == covenant["id"]
    }
    assert statuses == {
        "START": ("start", "accepted"),
        "daniels": ("step", "accepted"),
        "daniels_group_001": ("group", "accepted"),
        "daniels_collect_groups": ("collect_groups", "accepted"),
        "walter": ("step", "failed"),
        "END": ("end", "waiting"),
    }


async def test_graph_zoom(user: User, fixture_campaigns: list[dict]) -> None:
    """The graph zoom button switches the diagram between fitting the page and
    its natural size.
    """
    auriga = next(c for c in fixture_campaigns if c["name"] == "auriga")
    await open_campaign(user, auriga)
    set_expanded(user, "Campaign Graph", value=True)

    def diagram() -> str:
        graph = expansion(user, "Campaign Graph")
        return next(e for e in graph.descendants() if isinstance(e, ui.mermaid)).content

    assert "useMaxWidth" not in diagram()
    click(user, user.find(kind=ui.button, content="zoom_out_map").elements.pop())
    await user.should_see(kind=ui.button, content="zoom_in_map")
    assert "'useMaxWidth': false" in diagram()

    click(user, user.find(kind=ui.button, content="zoom_in_map").elements.pop())
    await user.should_see(kind=ui.button, content="zoom_out_map")
    assert "useMaxWidth" not in diagram()


async def test_drawer_nodes_view_toggle(user: User, auriga: dict) -> None:
    """The drawer's "Nodes As" toggle switches between node cards and a node
    table.
    """
    await open_drawer(user)
    with user.scope(kind=ui.right_drawer):
        nodes_as = user.find(kind=ui.toggle).elements.pop()
    assert nodes_as.value == "cards"

    # the browser reports the index of the chosen option
    trigger(user, nodes_as, "update:modelValue", 1)
    await user.should_see(kind=ui.table)
    table = user.find(kind=ui.table).elements.pop()
    assert {row["name"] for row in table.rows} == AURIGA_NODES
    assert {row["status"] for row in table.rows} == {"waiting"}
    assert node_cards(user) == {}

    trigger(user, nodes_as, "update:modelValue", 0)
    await user.should_not_see(kind=ui.table)
    assert set(node_cards(user)) == AURIGA_NODES


async def test_prepared_step_graph(user: User, cm_api: FakeCMService, fixture_campaigns: list[dict]) -> None:
    """The sulaco campaign's hicks step has a completed subgraph, and its
    failed hudson step, which had prepared before it failed, has a subgraph of
    waiting nodes.
    """
    sulaco = next(c for c in fixture_campaigns if c["name"] == "sulaco")
    await open_campaign(user, sulaco)
    graph = set_expanded(user, "Campaign Graph", value=True)
    mermaid = next(e for e in graph.descendants() if isinstance(e, ui.mermaid))

    expected_edges = {
        ("START", "hicks"),
        ("hicks", "hicks_group_001"),
        ("hicks", "hicks_group_002"),
        ("hicks_group_001", "hicks_collect_groups"),
        ("hicks_group_002", "hicks_collect_groups"),
        ("hicks_collect_groups", "hudson"),
        ("hudson", "hudson_group_001"),
        ("hudson", "hudson_group_002"),
        ("hudson_group_001", "hudson_collect_groups"),
        ("hudson_group_002", "hudson_collect_groups"),
        ("hudson_collect_groups", "END"),
    }
    edges = set(re.findall(r"(\S+) --> (\S+);", mermaid.content))
    assert edges == {(f"{s}.1", f"{t}.1") for s, t in expected_edges}

    statuses = {
        n["name"]: (n["kind"], n["status"]) for n in cm_api.nodes.values() if n["namespace"] == sulaco["id"]
    }
    assert statuses == {
        "START": ("start", "accepted"),
        "hicks": ("step", "accepted"),
        "hicks_group_001": ("group", "accepted"),
        "hicks_group_002": ("group", "accepted"),
        "hicks_collect_groups": ("collect_groups", "accepted"),
        "hudson": ("step", "failed"),
        "hudson_group_001": ("group", "waiting"),
        "hudson_group_002": ("group", "waiting"),
        "hudson_collect_groups": ("collect_groups", "waiting"),
        "END": ("end", "waiting"),
    }
    assert set(node_cards(user)) == set(statuses)
