"""Tests for the New Campaign page, reached from the campaign overview page.

The page's graph canvas is a JavaScript component that the simulated user
cannot see or operate; these tests cover the rest of the page.
"""

import asyncio
from typing import NamedTuple
from uuid import uuid5

import pytest
import yaml
from nice_dialogs.dialogs import LabelMakerDialog
from nicegui import ui
from nicegui.testing.user import User
from nicegui.testing.user_interaction import UserInteraction

from lsst.cmservice.models.enums import DEFAULT_NAMESPACE
from lsst.cmservice.web.lib.models import KIND_TO_SPEC

from .conftest import FakeCMService
from .interactions import (
    FakeCanvas,
    acting_as,
    click,
    eventually,
    node_cards,
    open_dialogs,
    open_drawer,
    wait_for_navigation,
)
from .mocks import ManifestLoader


async def open_new_campaign(user: User) -> None:
    """Navigate from the campaign overview page to the New Campaign page with
    the overview's "+" button.
    """
    await user.open("/")
    await user.should_see("Campaign Overview")
    click(user, next(b for b in user.find(kind=ui.button).elements if b.props.get("icon") == "add"))
    await wait_for_navigation(user, "/new_campaign")
    await user.should_see(kind=ui.input, content="Campaign Name", retries=30)


def footer_campaign_id(user: User) -> str:
    """The campaign ID shown in the page footer."""
    footer = user.find(kind=ui.footer).elements.pop()
    return str(next(e.text for e in footer.descendants() if type(e) is ui.label))


def manifests_section(user: User) -> ui.expansion:
    return user.find(kind=ui.expansion, content="Configuration Manifests").elements.pop()


def manifest_cards(user: User) -> dict[str, str]:
    """The kind and name of each manifest card in the manifests section, by
    manifest name.
    """
    cards = {}
    for card in manifests_section(user).descendants():
        if isinstance(card, ui.card):
            descendants = list(card.descendants())
            kind = next(e.text for e in descendants if isinstance(e, ui.chip))
            name = next(e.value for e in descendants if isinstance(e, ui.input))
            cards[name] = kind
    return cards


async def test_new_campaign_page(user: User) -> None:
    """From the overview's "+" button, the user gets a New Campaign page,
    names the campaign, chooses a notification label, and opens the manifest
    editor for a new manifest.
    """
    await open_new_campaign(user)
    await user.should_see(kind=ui.label, content="New Campaign")

    # the campaign has a default name, and its ID, shown in the footer, is
    # derived from the name, which is in snake case
    name = user.find(kind=ui.input, content="Campaign Name").elements.pop()
    assert name.value == "new_campaign"
    await eventually(
        lambda: footer_campaign_id(user), lambda value: value == str(uuid5(DEFAULT_NAMESPACE, "new_campaign"))
    )
    for new_name, snake_name in (("prometheus", "prometheus"), ("Prometheus Mission", "Prometheus_Mission")):
        with acting_as(user):
            name.set_value(new_name)
        # the input shows the snake case name once its binding is refreshed
        await eventually(lambda: name.value, lambda value: value == snake_name)
        expected_id = str(uuid5(DEFAULT_NAMESPACE, snake_name))
        await eventually(lambda: footer_campaign_id(user), lambda value: value == expected_id)

    # the "default" notification label is available, and can be chosen
    labels = user.find(kind=ui.select, content="Notification Labels").elements.pop()
    assert labels.options == ["default"]
    assert labels.value == []
    with acting_as(user):
        UserInteraction(user, {labels}, None).click()  # open the popup
        UserInteraction(user, {labels}, "default").click()  # choose the option
        UserInteraction(user, {labels}, None).click()  # close the popup
    assert labels.value == ["default"]

    # with no library manifests, the manifests section is empty except for
    # its "+" button, which opens the manifest editor for a new manifest
    assert manifest_cards(user) == {}
    editor = await open_manifest_editor(user)
    editor_element(editor, ui.label, text="Manifest Editor")
    name_input = editor_element(editor, ui.input, label="Name")
    kind_select = editor_element(editor, ui.select, label="Kind")
    assert (name_input.enabled, kind_select.enabled) == (True, True)

    # cancelling the editor adds no manifest
    click(user, editor_element(editor, ui.button, text="Cancel"))
    await eventually(lambda: open_dialogs(user), lambda d: not d)
    assert manifest_cards(user) == {}


async def test_manifests_seeded_from_library(user: User, cm_api: FakeCMService) -> None:
    """The campaign's manifests are seeded from the library's default
    manifest of each kind, if any; other library manifests are not used.
    """
    cm_api.add_manifest(
        "lsst",
        "w_latest",
        spec={"lsst_version": "w_latest", "lsst_distrib_dir": "/path/to/lsst/distrib/w_latest"},
        default=True,
    )
    cm_api.add_manifest("wms", "htcondor", spec={"batch_system": "htcondor"}, default=True)
    cm_api.add_manifest("wms", "panda", spec={"batch_system": "panda"})

    await open_new_campaign(user)
    assert manifest_cards(user) == {"w_latest": "LSST", "htcondor": "WMS"}


MANIFEST_KINDS = sorted(set(KIND_TO_SPEC) - {"step"})
"""The kinds of manifest that the manifest editor can create."""


async def open_manifest_editor(user: User) -> ui.dialog:
    """Open the manifest editor for a new manifest with the "+" button of the
    New Campaign page's manifests section.
    """
    section = manifests_section(user)
    click(
        user,
        next(b for b in section.descendants() if isinstance(b, ui.button) and b.props.get("icon") == "add"),
    )
    return (await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1))[0]


def editor_element[T: ui.element](editor: ui.dialog, kind: type[T], **props: str) -> T:
    """Find an element of the manifest editor by its kind and properties or
    text.
    """
    for e in editor.descendants():
        if isinstance(e, kind) and all(
            e.props.get(k) == v or getattr(e, k, None) == v for k, v in props.items()
        ):
            return e
    msg = f"No {kind.__name__} with {props} in the editor"
    raise AssertionError(msg)


async def fill_in_new_manifest(user: User, editor: ui.dialog, name: str, kind: str) -> dict:
    """Enter a new manifest's name, select its kind, and apply its kind's
    template, returning the template from the code editor.
    """
    name_input = editor_element(editor, ui.input, label="Name")
    kind_select = editor_element(editor, ui.select, label="Kind")
    assert kind in kind_select.options
    with acting_as(user):
        UserInteraction(user, {name_input}, None).type(name)
        UserInteraction(user, {kind_select}, None).click()  # open the popup
        UserInteraction(user, {kind_select}, kind).click()  # choose the kind
    assert kind_select.value == kind

    code = editor_element(editor, ui.codemirror)
    assert code.value == "# Apply a template or freestyle some YAML"
    click(user, editor_element(editor, ui.button, text="Apply Template"))
    value = await eventually(lambda: str(code.value), lambda v: not v.startswith("#"))
    template = yaml.safe_load(value)
    assert isinstance(template, dict)
    return template


@pytest.mark.parametrize("kind", MANIFEST_KINDS)
async def test_new_manifest_from_template(user: User, kind: str) -> None:
    """In the manifest editor for a new manifest, the user enters a name,
    selects a kind, and applies the kind's template, which fills the code
    editor with the kind's fields and their examples or defaults. The template
    is valid, so validating it enables the "Done" button, which adds the
    manifest to the campaign.
    """
    await open_new_campaign(user)
    editor = await open_manifest_editor(user)
    template = await fill_in_new_manifest(user, editor, "muthur", kind)

    # the template has every field of the kind's model that is not excluded
    # or deprecated
    fields = {
        name
        for name, info in KIND_TO_SPEC[kind].model_fields.items()
        if not (info.exclude or info.deprecated)
    }
    assert set(template) == fields

    # the template has not been validated, so it cannot yet be used
    chip = editor_element(editor, ui.chip, text="Not validated")
    done = editor_element(editor, ui.button, text="Done")
    assert not done.enabled

    # validating the template lights up the "Done" button
    click(user, chip)
    await eventually(lambda: chip.text, lambda text: text == "Valid!")
    assert chip.props["color"] == "positive"
    await eventually(lambda: done.enabled, bool)

    # "Done" adds the manifest to the campaign
    click(user, done)
    await eventually(lambda: open_dialogs(user), lambda d: not d)
    await eventually(lambda: manifest_cards(user), lambda cards: cards == {"muthur": kind.upper()})


async def test_butler_manifest_template(user: User) -> None:
    """The template for a butler manifest uses the first example of each of
    the butler manifest's fields.
    """
    await open_new_campaign(user)
    editor = await open_manifest_editor(user)
    template = await fill_in_new_manifest(user, editor, "muthur", "butler")
    assert template == {
        "collections": {
            "campaign_input": ["LSSTCam/defaults"],
            "campaign_public_output": "u/{{ bps.operator }}/{{ lsst.campaign }}",
            "campaign_output": "u/{{ bps.operator }}/{{ lsst.campaign }}/out",
        },
        "predicates": ["instrument='LSSTCam'", "skymap='lsst_cells_v2'"],
        "repo": "/repo/main",
        "include_files": ["${DRP_PIPE_DIR}/includes/butler/repo_tuned_butler.yaml"],
    }


class ManifestEditorState(NamedTuple):
    """The validation state shown by the manifest editor."""

    chip_text: str
    chip_color: str
    done_enabled: bool
    log_visible: bool


def editor_state(editor: ui.dialog) -> ManifestEditorState:
    chip = next(e for e in editor.descendants() if isinstance(e, ui.chip) and e.props.get("outline"))
    return ManifestEditorState(
        chip_text=chip.text,
        chip_color=chip.props["color"],
        done_enabled=bool(editor_element(editor, ui.button, text="Done").enabled),
        log_visible=editor_element(editor, ui.log).visible,
    )


def error_log(editor: ui.dialog) -> list[str]:
    """The lines of the manifest editor's error log."""
    return [str(getattr(e, "text", "")) for e in editor_element(editor, ui.log).descendants()]


NOT_VALIDATED = ManifestEditorState("Not validated", "accent", done_enabled=False, log_visible=False)
VALID = ManifestEditorState("Valid!", "positive", done_enabled=True, log_visible=False)
INVALID = ManifestEditorState("Invalid!", "negative", done_enabled=False, log_visible=True)


async def edit_and_validate(user: User, editor: ui.dialog, text: str) -> None:
    """Replace the code editor's YAML as the user, then validate it."""
    code = editor_element(editor, ui.codemirror)
    with acting_as(user):
        code.set_value(text)
    # an edit makes the manifest unvalidated, so it cannot be used
    await eventually(lambda: editor_state(editor), lambda state: state == NOT_VALIDATED)
    chip = next(e for e in editor.descendants() if isinstance(e, ui.chip) and e.props.get("outline"))
    click(user, chip)


@pytest.mark.parametrize(
    ("invalid_yaml", "expected_errors"),
    [
        pytest.param("repo: [unclosed", ["Invalid YAML: while parsing a flow sequence"], id="invalid YAML"),
        pytest.param(
            "repo: /repo/main\nreop: /repo/main\n",
            [
                "2 validation errors for ButlerSpec",
                "Extra inputs are not permitted",
                "This is not a good spec.",
            ],
            id="invalid spec",
        ),
    ],
)
async def test_invalid_manifest_edit(user: User, invalid_yaml: str, expected_errors: list[str]) -> None:
    """A user edit to a valid manifest that fails validation makes the chip
    show it is invalid and the error log show why, and keeps the "Done"
    button disabled until the user corrects the manifest and validates it.
    """
    await open_new_campaign(user)
    editor = await open_manifest_editor(user)
    template = await fill_in_new_manifest(user, editor, "muthur", "butler")
    valid_yaml = yaml.safe_dump(template, width=160)

    await edit_and_validate(user, editor, valid_yaml)
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)

    # the invalid edit fails validation, with its errors in the log
    await edit_and_validate(user, editor, invalid_yaml)
    await eventually(lambda: editor_state(editor), lambda state: state == INVALID)
    log = "\n".join(error_log(editor))
    assert all(error in log for error in expected_errors), log

    # "Done" stays disabled while the manifest remains invalid
    await edit_and_validate(user, editor, invalid_yaml + "\n# still broken\n")
    await eventually(lambda: editor_state(editor), lambda state: state == INVALID)

    # correcting the manifest and validating it enables "Done" again, and
    # hides the error log
    await edit_and_validate(user, editor, valid_yaml)
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "EditorDialog.validate_editor rewrites a valid manifest's YAML in canonical form after "
        "validating it; when that changes the text, the editor's change handler then resets the "
        "chip to 'Not validated' and disables 'Done', so the user must validate again."
    ),
)
async def test_validate_non_canonical_yaml(user: User) -> None:
    """Valid YAML that is not in the editor's canonical form validates with a
    single click.
    """
    await open_new_campaign(user)
    editor = await open_manifest_editor(user)
    template = await fill_in_new_manifest(user, editor, "muthur", "butler")
    # the same manifest, but with the repository indented differently
    non_canonical_yaml = yaml.safe_dump(template, width=160).replace("repo: ", "repo:    ")

    await edit_and_validate(user, editor, non_canonical_yaml)
    await asyncio.sleep(0.5)
    assert editor_state(editor) == VALID


async def open_step_editor(user: User, campaign_name: str, step_name: str) -> tuple[FakeCanvas, ui.dialog]:
    """On the New Campaign page, name the campaign and, on a canvas with a
    single step between START and END, click the step to open its editor.
    """
    await open_new_campaign(user)
    with acting_as(user):
        user.find(kind=ui.input, content="Campaign Name").elements.pop().set_value(campaign_name)
    campaign_id = str(uuid5(DEFAULT_NAMESPACE, campaign_name))
    await eventually(lambda: footer_campaign_id(user), lambda value: value == campaign_id)

    canvas = FakeCanvas.with_steps(user, step_name)
    canvas.click_node("n1")
    editor = (await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1))[0]
    editor_element(editor, ui.label, text="New Step Editor")
    return canvas, editor


def editor_spec(editor: ui.dialog) -> dict:
    """The spec in the editor's code editor."""
    spec = yaml.safe_load(str(editor_element(editor, ui.codemirror).value))
    assert isinstance(spec, dict)
    return spec


async def close_editor(user: User, editor: ui.dialog, button: str) -> None:
    """Close an editor with its "Done" or "Cancel" button."""
    click(user, editor_element(editor, ui.button, text=button))
    await eventually(lambda: open_dialogs(user), lambda d: not d)


async def reopen_step(user: User, canvas: FakeCanvas, node_id: str) -> ui.dialog:
    """Click a step on the canvas to open its editor again."""
    canvas.click_node(node_id)
    return (await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1))[0]


async def save_campaign(user: User, campaign_name: str) -> str:
    """Save the campaign with the side panel's "Save" button, and wait for the
    new campaign's detail page to open. Returns the campaign's ID.
    """
    await open_drawer(user)
    click(user, user.find(kind=ui.button, content="Save").elements.pop())
    campaign_id = str(uuid5(DEFAULT_NAMESPACE, campaign_name))
    await wait_for_navigation(user, f"/campaign/{campaign_id}")
    return campaign_id


STEP_SPEC = {
    "bps": {"pipeline_yaml": "${DRP_PIPE_DIR}/pipelines/LSSTCam/DRP.yaml#step1"},
    "groups": None,
}
"""The spec of a simple step, without groups."""


async def test_one_step_campaign(user: User, cm_api: FakeCMService) -> None:
    """In a new campaign with a single step between START and END, clicking
    the step on the canvas opens the step editor, with the step's name, its
    fixed kind, and a starting spec. Cancelling the editor discards the user's
    edits; after the user is done with a spec, reopening the step shows it.
    The saved campaign has the step with the spec the user was done with.
    """
    loader = ManifestLoader(cm_api)
    canvas, editor = await open_step_editor(user, "prometheus", "bishop")

    # the step's name, from the canvas, and its kind cannot be changed
    name_input = editor_element(editor, ui.input, label="Name")
    kind_select = editor_element(editor, ui.select, label="Kind")
    assert name_input.value == "bishop"
    assert not name_input.enabled
    assert kind_select.value == "step"
    await eventually(lambda: kind_select.enabled, lambda enabled: not enabled)

    # the editor starts with a placeholder spec for a step without groups
    placeholder_spec = {
        "bps": {"pipeline_yaml": "${DRP_PIPE_DIR}/path/to/file.yaml#anchor"},
        "groups": None,
    }
    assert editor_spec(editor) == placeholder_spec
    for control in ("Edit Selectors", "Grouping"):
        editor_element(editor, ui.element, text=control)
    assert editor_state(editor) == NOT_VALIDATED

    # the user edits and validates the spec, but cancels the editor, so
    # reopening the step shows the placeholder spec again
    cancelled_spec = {"bps": {"pipeline_yaml": "${DRP_PIPE_DIR}/pipelines/LSSTCam/DRP.yaml#cancelled"}}
    await edit_and_validate(user, editor, yaml.safe_dump(cancelled_spec, width=160))
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)
    await close_editor(user, editor, "Cancel")
    editor = await reopen_step(user, canvas, "n1")
    assert editor_spec(editor) == placeholder_spec
    assert editor_state(editor) == NOT_VALIDATED

    # the user edits and validates the spec, and is done with the step
    await edit_and_validate(user, editor, yaml.safe_dump(STEP_SPEC, width=160))
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)
    await close_editor(user, editor, "Done")

    # reopening the step shows the spec the user was done with, which must
    # be validated again before the user can be done with it
    editor = await reopen_step(user, canvas, "n1")
    assert editor_element(editor, ui.input, label="Name").value == "bishop"
    assert editor_spec(editor) == STEP_SPEC
    assert editor_state(editor) == NOT_VALIDATED

    # changes to the spec are discarded when the reopened editor is cancelled
    await edit_and_validate(user, editor, yaml.safe_dump(cancelled_spec, width=160))
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)
    await close_editor(user, editor, "Cancel")
    editor = await reopen_step(user, canvas, "n1")
    assert editor_spec(editor) == STEP_SPEC
    await close_editor(user, editor, "Cancel")

    # saving the campaign exports the canvas and saves the campaign, its step,
    # and its edges, then opens the new campaign's detail page
    campaign_id = await save_campaign(user, "prometheus")
    assert canvas.exports == 1
    assert [m["kind"] for m in loader.manifests] == ["campaign", "node", "edge", "edge"]

    bishop = next(n for n in cm_api.nodes.values() if n["namespace"] == campaign_id and n["name"] == "bishop")
    assert (bishop["kind"], bishop["version"], bishop["configuration"]) == ("step", 1, STEP_SPEC)
    names = {n["id"]: n["name"] for n in cm_api.nodes.values()}
    assert {(names[s], names[t]) for s, t in cm_api.edges[campaign_id]} == {
        ("START", "bishop"),
        ("bishop", "END"),
    }

    await user.should_see("Campaign Graph", retries=20)
    assert set(node_cards(user)) == {"START", "bishop", "END"}


GROUPING_CASES = [
    # the steps of the `test_campaign_groups` fixture of the CM Service tests
    pytest.param(
        "grouping_none",
        "${WEYLAND_YUTANI}/personnel/commissioned.yaml#navigator",
        None,
        None,
        id="no grouping (lambert)",
    ),
    pytest.param(
        "grouping_fixed",
        "${WEYLAND_YUTANI}/personnel/synthetic.yaml",
        {"split_by": "values", "dimension": None, "values": []},
        {
            "split_by": "values",
            "dimension": "xenomorph",
            "values": [1234, [2345, 3456, 4567], "facehugger", {"min": 5678, "max": 6789, "endpoint": True}],
        },
        id="fixed-value grouping (ash)",
    ),
    pytest.param(
        "grouping_query",
        "${WEYLAND_YUTANI}/personnel/commissioned.yaml#warrant_officer",
        {"split_by": "query", "dataset": None, "dimension": None, "min_groups": 1, "max_size": 0},
        {
            "split_by": "query",
            "dataset": "species",
            "dimension": "xenomorph",
            "min_groups": 4,
            "max_size": 1_000_000,
        },
        id="query grouping (ripley)",
    ),
]


@pytest.mark.parametrize(("grouping", "pipeline_yaml", "template", "groups"), GROUPING_CASES)
async def test_step_grouping(
    user: User,
    cm_api: FakeCMService,
    grouping: str,
    pipeline_yaml: str,
    template: dict | None,
    groups: dict | None,
) -> None:
    """The step editor's "Grouping" menu applies a grouping template to the
    step's spec, keeping the rest of the spec. A template for fixed-value or
    query grouping has placeholders that the user must fill in for the spec to
    be valid. The saved step has the user's grouping.
    """
    ManifestLoader(cm_api)
    _, editor = await open_step_editor(user, "nostromo", "bishop")
    code = editor_element(editor, ui.codemirror)
    base_spec = {"bps": {"pipeline_yaml": pipeline_yaml}, "predicates": ["skymap='lv_426'"]}
    with acting_as(user):
        code.set_value(yaml.safe_dump(base_spec, width=160))

    # the grouping template is applied to the spec in the editor
    item = next(e for e in editor.descendants() if isinstance(e, ui.item) and e.props.get("id") == grouping)
    click(user, item)
    await eventually(lambda: yaml.safe_load(str(code.value)), lambda spec: "groups" in spec)
    assert yaml.safe_load(str(code.value)) == base_spec | {"groups": template}

    chip = next(e for e in editor.descendants() if isinstance(e, ui.chip) and e.props.get("outline"))
    click(user, chip)
    if template is None:
        # no grouping is complete as it is
        await eventually(lambda: editor_state(editor), lambda state: state == VALID)
    else:
        # the template's placeholders must be filled in
        await eventually(lambda: editor_state(editor), lambda state: state == INVALID)
        assert "validation errors for StepSpec" in "\n".join(error_log(editor))

        await edit_and_validate(user, editor, yaml.safe_dump(base_spec | {"groups": groups}, width=160))
        await eventually(lambda: editor_state(editor), lambda state: state == VALID)

    click(user, editor_element(editor, ui.button, text="Done"))
    await eventually(lambda: open_dialogs(user), lambda d: not d)

    campaign_id = await save_campaign(user, "nostromo")
    bishop = next(n for n in cm_api.nodes.values() if n["namespace"] == campaign_id and n["name"] == "bishop")
    assert bishop["configuration"] == base_spec | {"groups": groups}


SELECTORS = {"butler": {"vessel": "nostromo"}, "site": {"compute-site": "mock"}}
"""The manifest selectors of the lambert step of the `test_campaign_groups`
fixture of the CM Service tests.
"""


def label_maker(user: User) -> LabelMakerDialog:
    """The open label maker dialog, used to edit a manifest's labels or a
    step's manifest selectors.
    """
    return next(d for d in open_dialogs(user) if isinstance(d, LabelMakerDialog))


def label_chips(dialog: LabelMakerDialog) -> list[str]:
    """The entries on the label maker dialog's list, in order."""
    return [str(e.text) for e in dialog.descendants() if isinstance(e, ui.chip)]


def marked[T: ui.element](dialog: LabelMakerDialog, marker: str, kind: type[T]) -> list[T]:
    """The label maker dialog's elements with a marker."""
    return [e for e in dialog.descendants() if marker in e._markers and isinstance(e, kind)]


async def open_label_maker(user: User, editor: ui.dialog, button: str) -> LabelMakerDialog:
    """Open a label maker dialog with one of the editor's buttons."""
    click(user, editor_element(editor, ui.button, text=button))
    await eventually(lambda: [d for d in open_dialogs(user) if isinstance(d, LabelMakerDialog)], bool)
    return label_maker(user)


async def enter_label(user: User, dialog: LabelMakerDialog, *values: str) -> None:
    """Enter the values of a label maker entry, choosing each value from a
    select input's options or typing it into a text input, and add it to the
    dialog's list.
    """
    with acting_as(user):
        for i, value in enumerate(values):
            element = marked(dialog, f"input_{i}", ui.element)[0]
            if isinstance(element, ui.select):
                UserInteraction(user, {element}, None).click()  # open the popup
                UserInteraction(user, {element}, value).click()  # choose the option
            else:
                assert isinstance(element, ui.input)
                element.set_value(value)
    add = marked(dialog, "add", ui.button)[0]
    await eventually(lambda: add.enabled, bool)
    count = len(label_chips(dialog))
    click(user, add)
    await eventually(lambda: len(label_chips(dialog)), lambda n: n == count + 1)


async def delete_label(user: User, dialog: LabelMakerDialog, chip_text: str) -> None:
    """Delete an entry from the label maker dialog's list."""
    index = label_chips(dialog).index(chip_text)
    item = marked(dialog, f"label_{index}", ui.item)[0]
    click(user, next(e for e in item.descendants() if "delete" in e._markers))
    await eventually(lambda: label_chips(dialog), lambda chips: chip_text not in chips)


async def test_step_selectors(user: User, cm_api: FakeCMService) -> None:
    """The step editor's "Edit Selectors" button opens a dialog where the user
    adds selectors of manifests by kind, name, and value to a list, from which
    they can be deleted or edited. Submitting the list applies the selectors
    to the step, and the saved step has them in its metadata.
    """
    ManifestLoader(cm_api)
    canvas, editor = await open_step_editor(user, "nostromo", "lambert")
    await edit_and_validate(user, editor, yaml.safe_dump(STEP_SPEC, width=160))
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)

    # the selector dialog starts with an empty list, and a selector can only
    # be added once its manifest kind, name, and value are entered
    dialog = await open_label_maker(user, editor, "Edit Selectors")
    assert any(type(e) is ui.label and e.text == "Manifest Selectors" for e in dialog.descendants())
    assert label_chips(dialog) == []
    kind_select = marked(dialog, "input_0", ui.select)[0]
    assert kind_select.options == ["bps", "butler", "lsst", "site", "wms"]
    assert [marked(dialog, f"input_{i}", ui.element)[0].props["label"] for i in range(3)] == [
        "Manifest Kind",
        "Selector Name",
        "Selector Value",
    ]
    await eventually(lambda: marked(dialog, "add", ui.button)[0].enabled, lambda enabled: not enabled)

    # the user adds three selectors
    await enter_label(user, dialog, "butler", "vessel", "nostromo")
    await enter_label(user, dialog, "site", "compute-site", "slac")
    await enter_label(user, dialog, "wms", "batch-system", "htcondor")
    assert label_chips(dialog) == [
        "butler : vessel : nostromo",
        "site : compute-site : slac",
        "wms : batch-system : htcondor",
    ]

    # and deletes one
    await delete_label(user, dialog, "wms : batch-system : htcondor")
    assert label_chips(dialog) == ["butler : vessel : nostromo", "site : compute-site : slac"]

    # to edit a selector, the user clicks it to copy it to the inputs, changes
    # it, adds it, and deletes the original
    click(user, next(e for e in dialog.descendants() if isinstance(e, ui.chip) and e.text.startswith("site")))
    inputs = [marked(dialog, f"input_{i}", ui.element)[0] for i in range(3)]
    assert [getattr(e, "value", None) for e in inputs] == ["site", "compute-site", "slac"]
    await enter_label(user, dialog, "site", "compute-site", "mock")
    await delete_label(user, dialog, "site : compute-site : slac")
    assert label_chips(dialog) == ["butler : vessel : nostromo", "site : compute-site : mock"]

    # submitting the list closes the selector dialog, leaving the step editor
    click(user, marked(dialog, "submit", ui.button)[0])
    await eventually(lambda: open_dialogs(user), lambda d: d == [editor])

    # the selectors are applied to the step, so the user's selectors are
    # listed when the dialog is opened again, although not necessarily in the
    # same order, as the step keeps them by manifest kind; cancelling the
    # dialog changes nothing
    dialog = await open_label_maker(user, editor, "Edit Selectors")
    assert sorted(label_chips(dialog)) == ["butler : vessel : nostromo", "site : compute-site : mock"]
    click(user, marked(dialog, "cancel", ui.button)[0])
    await eventually(lambda: open_dialogs(user), lambda d: d == [editor])

    # the user is done with the step, and saves the campaign; the saved step
    # has the selectors in its metadata
    await close_editor(user, editor, "Done")
    campaign_id = await save_campaign(user, "nostromo")
    lambert = next(
        n for n in cm_api.nodes.values() if n["namespace"] == campaign_id and n["name"] == "lambert"
    )
    assert lambert["metadata"]["selectors"] == SELECTORS
    assert lambert["configuration"] == STEP_SPEC


async def test_manifest_labels(user: User, cm_api: FakeCMService) -> None:
    """The manifest editor's "Edit Labels" button opens a dialog where the user
    adds labels, as names and values, to a list, from which they can be
    deleted or edited. Submitting the list applies the labels to the manifest.
    A step selects the manifest by its kind and labels, so a step whose
    selector matches the saved manifest's labels selects it.
    """
    ManifestLoader(cm_api)
    await open_new_campaign(user)
    with acting_as(user):
        user.find(kind=ui.input, content="Campaign Name").elements.pop().set_value("nostromo")
    campaign_id = str(uuid5(DEFAULT_NAMESPACE, "nostromo"))
    await eventually(lambda: footer_campaign_id(user), lambda value: value == campaign_id)

    editor = await open_manifest_editor(user)
    template = await fill_in_new_manifest(user, editor, "muthur", "butler")
    await edit_and_validate(user, editor, yaml.safe_dump(template, width=160))
    await eventually(lambda: editor_state(editor), lambda state: state == VALID)

    # the label dialog starts with an empty list, and has inputs for a label's
    # name and value but not a manifest kind
    dialog = await open_label_maker(user, editor, "Edit Labels")
    assert any(type(e) is ui.label and e.text == "Manifest Labels" for e in dialog.descendants())
    assert label_chips(dialog) == []
    inputs = [marked(dialog, f"input_{i}", ui.element) for i in range(3)]
    assert [type(e[0]) for e in inputs[:2]] == [ui.input, ui.input]
    assert inputs[2] == []
    assert [e[0].props["label"] for e in inputs[:2]] == ["Label Name", "Label Value"]
    await eventually(lambda: marked(dialog, "add", ui.button)[0].enabled, lambda enabled: not enabled)

    # the user adds three labels, deletes one, and edits another
    for name, value in (("vessel", "nostromo"), ("module", "romulus"), ("crew", "seven")):
        await enter_label(user, dialog, name, value)
    assert label_chips(dialog) == ["vessel : nostromo", "module : romulus", "crew : seven"]
    await delete_label(user, dialog, "crew : seven")
    click(
        user, next(e for e in dialog.descendants() if isinstance(e, ui.chip) and e.text.startswith("module"))
    )
    assert [marked(dialog, f"input_{i}", ui.input)[0].value for i in range(2)] == ["module", "romulus"]
    await enter_label(user, dialog, "module", "remus")
    await delete_label(user, dialog, "module : romulus")
    assert label_chips(dialog) == ["vessel : nostromo", "module : remus"]

    # submitting the list applies the labels to the manifest, which lists them
    # when the dialog is opened again
    click(user, marked(dialog, "submit", ui.button)[0])
    await eventually(lambda: open_dialogs(user), lambda d: d == [editor])
    dialog = await open_label_maker(user, editor, "Edit Labels")
    assert sorted(label_chips(dialog)) == ["module : remus", "vessel : nostromo"]
    click(user, marked(dialog, "cancel", ui.button)[0])
    await eventually(lambda: open_dialogs(user), lambda d: d == [editor])
    await close_editor(user, editor, "Done")
    assert manifest_cards(user) == {"muthur": "BUTLER"}

    # a step selects the butler manifest by one of its labels
    canvas = FakeCanvas.with_steps(user, "lambert")
    canvas.click_node("n1")
    step_editor = (await eventually(lambda: open_dialogs(user), lambda d: len(d) == 1))[0]
    await edit_and_validate(user, step_editor, yaml.safe_dump(STEP_SPEC, width=160))
    await eventually(lambda: editor_state(step_editor), lambda state: state == VALID)
    dialog = await open_label_maker(user, step_editor, "Edit Selectors")
    await enter_label(user, dialog, "butler", "vessel", "nostromo")
    click(user, marked(dialog, "submit", ui.button)[0])
    await eventually(lambda: open_dialogs(user), lambda d: d == [step_editor])
    await close_editor(user, step_editor, "Done")

    # the saved manifest has the labels, and the saved step's selector of
    # butler manifests matches them
    await save_campaign(user, "nostromo")
    muthur = next(
        m for m in cm_api.manifests.values() if m["namespace"] == campaign_id and m["name"] == "muthur"
    )
    assert muthur["kind"] == "butler"
    assert muthur["metadata"]["labels"] == {"vessel": "nostromo", "module": "remus"}
    lambert = next(
        n for n in cm_api.nodes.values() if n["namespace"] == campaign_id and n["name"] == "lambert"
    )
    assert lambert["metadata"]["selectors"] == {"butler": {"vessel": "nostromo"}}
    assert lambert["metadata"]["selectors"]["butler"].items() <= muthur["metadata"]["labels"].items()
