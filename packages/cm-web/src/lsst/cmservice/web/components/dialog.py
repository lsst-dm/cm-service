"""Module implementing reusable and/or modular Dialogs."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum, IntFlag, auto
from typing import TYPE_CHECKING, Any, Self

import yaml
from nicegui import ui
from nicegui.events import ClickEventArguments, GenericEventArguments, ValueChangeEventArguments
from pydantic_core import ValidationError

from lsst.cmservice.common.enums import DEFAULT_NAMESPACE

from .. import api
from ..lib.models import KIND_TO_SPEC, STEP_MANIFEST_TEMPLATE
from ..lib.parsers import as_snake_case
from ..pages.common import CMPage
from . import strings


class SpecValidationError(RuntimeError): ...


MaybeDict = dict[str, Any] | None
"""A shorthand type to indicate an optional dictionary with string keys."""


@dataclass
class EditorContext[PageT: CMPage]:
    page: PageT
    namespace: str = str(DEFAULT_NAMESPACE)
    name: str | None = None
    kind: str | None = None
    uuid: str | None = None
    valid: bool | None = None
    allow_kind_change: bool = True
    allow_name_change: bool = True
    readonly: bool = False
    callback: (
        Callable[[dict[str, Any]], MaybeDict] | Callable[[dict[str, Any]], Awaitable[MaybeDict]] | None
    ) = None
    name_validators: list[str] = field(default_factory=list)
    model: Any = field(default_factory=dict)


class NodeRecoverAction(Enum):
    """An enumeration of the actions that may be taken to recover a Node from
    a failed state.
    """

    cancel = auto()
    restart = auto()
    retry = auto()
    reset = auto()
    force = auto()


class NodeAllowedActions(IntFlag):
    """A flag enumeration declaring which recovery actions are allowed to be
    taken for a Node in a failed state. For example, only Group nodes may be
    subject to "restart" actions.
    """

    restart = auto()
    retry = auto()
    reset = auto()
    force = auto()

    @classmethod
    def all(cls) -> Self:
        """Creates a flag where all the available members are set."""
        return ~cls(0)


class NodeRecoveryPopup(ui.dialog):
    """A modal dialog presenting Node recovery options for a Node in a failed
    state.
    """

    def __init__(self, allowed_actions: NodeAllowedActions) -> None:
        super().__init__()
        with self, ui.card():
            ui.label(strings.NODE_RECOVERY_DIALOG_LABEL)
            with ui.row():
                if NodeAllowedActions.restart in allowed_actions:
                    ui.chip(
                        "restart",
                        icon="restart_alt",
                        color="positive",
                        on_click=lambda: self.submit(NodeRecoverAction.restart),
                    ).tooltip(strings.NODE_RESTART_TOOLTIP)
                if NodeAllowedActions.retry in allowed_actions:
                    ui.chip(
                        "retry",
                        icon="replay",
                        color="accent",
                        on_click=lambda: self.submit(NodeRecoverAction.retry),
                    ).tooltip(strings.NODE_RETRY_TOOLTIP)
                if NodeAllowedActions.reset in allowed_actions:
                    ui.chip(
                        "reset",
                        icon="settings_backup_restore",
                        color="negative",
                        on_click=lambda: self.submit(NodeRecoverAction.reset),
                    ).tooltip(strings.NODE_RESET_TOOLTIP)
                if NodeAllowedActions.force in allowed_actions:
                    ui.chip(
                        "accept",
                        icon="auto_fix_high",
                        color="warning",
                        on_click=lambda: self.submit(NodeRecoverAction.force),
                    ).tooltip(strings.NODE_FORCE_TOOLTIP)
                ui.chip(
                    "cancel",
                    icon="cancel",
                    color="negative",
                    on_click=lambda: self.submit(NodeRecoverAction.cancel),
                ).tooltip("Never mind.")

    @classmethod
    async def click(cls, e: GenericEventArguments, node: dict, refreshable: Callable) -> None:
        """Callback method for a click event from an element on a Node Recovery
        Popup dialog.
        """
        if TYPE_CHECKING:
            assert hasattr(refreshable, "refresh")

        allowed_actions = NodeAllowedActions.all()
        call_refreshable = True
        if node["kind"] == "breakpoint":
            allowed_actions = NodeAllowedActions.force
        elif node["kind"] != "group":
            allowed_actions &= ~NodeAllowedActions.restart
        result = await cls(allowed_actions)

        match result:
            case NodeRecoverAction.restart:
                await api.retry_restart_node(n0=node["id"], force=True)
            case NodeRecoverAction.retry:
                await api.retry_restart_node(n0=node["id"], force=False)
            case NodeRecoverAction.reset:
                await api.retry_restart_node(n0=node["id"], force=True, reset=True)
            case NodeRecoverAction.force:
                await api.retry_restart_node(n0=node["id"], force=True, accept=True)
            case _:
                # including the cancel case
                call_refreshable = False

        if call_refreshable:
            refreshable.refresh()


class EditorDialog(ui.dialog):
    """A modal dialog presenting an editor for manifests of varying types in
    different page contexts.
    """

    context: EditorContext[CMPage]
    editor: ui.codemirror
    error_log: ui.log
    validation_handlers: list[str] = []
    name_input: ui.input
    kind_selector: ui.select
    splitter: ui.splitter

    def __init__(
        self,
        ctx: EditorContext,
        *,
        title: str = "Manifest Editor",
        initial_model: dict | None = None,
    ) -> None:
        super().__init__()
        self.props("maximized")
        self.context = ctx
        # FIXME just use the pydantic manifest model
        if initial_model is None:
            self.context.model = deepcopy(STEP_MANIFEST_TEMPLATE)
            self.context.model["metadata"]["namespace"] = str(ctx.namespace)
            self.context.model["metadata"]["name"] = ctx.name
            self.context.model["metadata"]["kind"] = ctx.kind
            self.context.model["metadata"]["uuid"] = ctx.uuid
            self.context.model["spec"] = {}
        else:
            # We deepcopy this model so we don't leak edits back to any other
            # objects
            self.context.model = deepcopy(initial_model)

        self.dialog_content(title)

    def dialog_content(self, title: str) -> None:
        """Method creates core dialog components."""
        with (
            self,
            ui.card().classes(
                "w-[96vw] h-[85vh] max-w-[96vm] max-h-[85vh] "
                "flex flex-col flex-nowrap "
                "overflow-y-scroll overflow-x-hidden"
            ),
        ):
            with ui.row().classes("w-full max-w-full mb-1 items-baseline"):
                ui.label(title).classes("flex-none text-subtitle1")
                ui.space()
                ui.button(icon="help", color="info", on_click=self.toggle_help_pane).classes(
                    "flex-none"
                ).props("fab flat").tooltip("Toggle help pane")

            with ui.row().classes("w-full max-w-full mb-1 items-baseline"):
                self.ribbon()

            with ui.splitter(limits=(50, 100), value=100).classes(
                "w-full h-full max-w-full min-h-[4rem]"
            ) as self.splitter:
                with self.splitter.before:
                    self.editor_section()
                with self.splitter.after:
                    self.help_section()
                with self.splitter.separator:
                    ui.icon("help", color="info").classes("bg-white rounded-full p-1").tooltip(
                        "Drag for help"
                    )

            self.action_section()

    def ribbon(self) -> None:
        """A row of controls available to the dialog.

        Subclasses should override this method to provide different context
        operations for the dialog.
        """
        # Generic Editor ribbon includes a -name- input with a standard
        # debounced validator.
        self.create_name_input()
        self.create_kind_selector()
        self.namespace_input()

    @ui.refreshable_method
    def editor_section(self) -> None:
        """Provides an editor component with a validation button, together in
        a column. An error log component can be used to communicate validation
        or other information, and it is displayed whenever the editor is in an
        invalid state, and auto-hides when valid or unvalidated content is
        present.
        """
        # NOTE that the value of the editor component is not bound to the model
        # because the model is not updated until after validation. Because the
        # codemirror component does not implement a debounce or cleanly support
        # navigation events like blur, validation is left to an intentional
        # action tied to the validation chip which serves as both a button and
        # a status bar.
        with ui.column().classes("gap-0 border w-full h-full flex-col overflow-auto"):
            with ui.row().classes("w-full gap-2 grow min-h-[2rem]"):
                # When creating the editor, the value needs to be a string,
                # so we use a placeholder if the spec dict is empty
                initial_value = (
                    yaml.safe_dump(self.context.model["spec"])
                    if self.context.model["spec"]
                    else "# Apply a template or freestyle some YAML"
                )
                self.editor = (
                    ui.codemirror(
                        value=initial_value,
                        language="YAML",
                        highlight_whitespace=False,
                        on_change=self.changed_editor,
                    )
                    .classes("flex-1 mb-0 h-full!")
                    .bind_enabled_from(self.context, target_name="readonly", backward=lambda v: not v)
                )
                self.error_log = (
                    ui.log()
                    .classes("flex-1 mb-0 h-full!")
                    .bind_visibility_from(self.context, "valid", backward=lambda v: v is False)
                )
            with ui.row().classes("w-full items-center gap-2 mt-0 shrink-0 min-h-[2rem]"):
                self.validation_chip = (
                    ui.chip(
                        "Not validated", icon="unpublished", on_click=self.validate_editor, color="accent"
                    )
                    .classes("w-full text-sm")
                    .tooltip("Click to Validate")
                    .props("outline square")
                    .bind_visibility_from(self.context, target_name="readonly", backward=lambda v: not v)
                )

    @ui.refreshable_method
    def help_section(self) -> None:
        with ui.element("div").classes("w-full h-full"):
            if self.context.kind is None:
                ui.label("No help available.")
                return None
            ui.element("iframe").props(f"src='/static/docs/{self.context.kind}_spec.html'").classes(
                "w-full h-full"
            )

    @ui.refreshable_method
    def action_section(self) -> None:
        with ui.card_actions().classes("flex-none"):
            ui.button(
                "Done",
                color="positive",
                on_click=self.done_callback,
            ).bind_enabled_from(self.context, "valid").props("flat")
            ui.button("Cancel", color="negative", on_click=lambda: self.submit(None)).props("flat")

    async def changed_editor(self, evt: ValueChangeEventArguments) -> None:
        """Callback for change events from editor component.

        NOTE: this is fired on every keystroke without a debounce, keep it
        cheap!
        """
        self.validation_chip.props("color=accent icon=help_outline")
        self.validation_chip.set_text("Not validated")
        self.context.valid = None

    async def validate_editor(self, evt: ClickEventArguments) -> None:
        """Callback from Validate button.

        Validates the content of the code editor and updates the validation
        chip button before updating the model.

        Additional validators can be added to the `validation_handlers` prop
        and within these, the content should be read from `self.model["spec"]`
        and should raise a `SpecValidationError` if validation fails.
        These additional validators can otherwise manipulate the `error_log`
        component as needed to communicate specific problems.

        The `validation_handlers` list is primarily meant for subclasses to
        implement specific validation callbacks or chains for the editor.
        """

        async def positive_validation() -> None:
            self.validation_chip.props("color=positive icon=check_circle")
            self.validation_chip.set_text("Valid!")
            self.context.valid = True

        async def negative_validation() -> None:
            self.validation_chip.props("color=negative icon=error")
            self.validation_chip.set_text("Invalid!")
            self.context.valid = False

        self.error_log.clear()
        self.error_log.update()
        try:
            yaml_spec = yaml.safe_load(self.editor.value)
            self.context.model["spec"] = yaml_spec
            for validator in self.validation_handlers:
                try:
                    validation_result = getattr(self, validator)()
                    if isinstance(validation_result, Awaitable):
                        await validation_result
                except AttributeError:
                    msg = f"Required validation handler not found: {validator}"
                    raise RuntimeError(msg)
            # Round trip the loaded spec back to yaml. This will reformat etc.
            self.editor.set_value(yaml.safe_dump(yaml_spec))
            self.editor.update()
            return await positive_validation()
        except yaml.YAMLError as e:
            self.error_log.push(f"Invalid YAML: {e}")
        except RuntimeError as e:
            self.error_log.push(e)

        return await negative_validation()

    async def toggle_help_pane(self, evt: ClickEventArguments) -> None:
        """Toggles the help pane to 50% if it's mostly closed already, other-
        wise closes the pane.
        """
        if self.splitter.value > 85:
            self.splitter.value = 50
        else:
            self.splitter.value = 100

    def create_name_input(self, label: str = "Name", debounce: int = 1_000) -> None:
        """Input field for the manifest's Name.

        This debounced component validates the input only after the debounce
        period (1 second by default) expires.

        The default validator checks for the presence of an input and formats/
        sanitizes it.

        If addtional `name_validators` are specified in the `EditorContext`
        object, these are called in order. These validators must be available
        on the page object referenced by the context and will be awaited as
        necessary. These extra validators may be used to fail validation by
        returning a string error message and must return None otherwise. These
        validators may not additionally modify the sanitized input.
        """

        async def validate_name(data: str | None) -> str | None:
            """Local function to validate and parse name input."""
            # Any time we validate the name value, start by clearing any names
            # being tracked in the context or model, so it will always be set
            # to the validated name
            self.context.model["metadata"]["name"] = None

            if data is None:
                return "Name is required"
            candidate_name = as_snake_case(data)

            for validator in self.context.name_validators:
                try:
                    r = getattr(self.context.page, validator)(candidate_name, self.context)
                    if isinstance(r, Awaitable):
                        r = await r
                    match r:
                        case None:
                            # None is the valid case
                            continue
                        case str():
                            # Any string response is an error message
                            return r
                        case _:
                            # Anything else is a broken validator
                            raise RuntimeError
                except (AttributeError, RuntimeError):
                    return f"Invalid validator: {validator}"
            self.context.model["metadata"]["name"] = candidate_name
            self.context.name = candidate_name
            return None

        # NOTE that the input value is bound to the context.name attribute so
        # may not be a valid name. Only the name applied to the spec model may
        # be considered valid
        self.name_input = (
            ui.input(label=label, validation=validate_name)
            .props(f"debounce={debounce}")
            .classes("flex-1")
            .bind_value(self.context, target_name="name")
            .bind_enabled_from(self.context, "allow_name_change")
        )

    def create_kind_selector(self, label: str = "Kind") -> None:
        """A dropdown selector indicating the kind of Manifest."""

        async def validate_kind(data: str | None) -> None:
            """Local validation callback for kind selector"""
            # trigger a new validation of the manifest name
            self.name_input.validate(return_result=False)

        self.kind_selector = (
            ui.select(
                options=list(KIND_TO_SPEC.keys()),
                label=label,
                validation=validate_kind,
                on_change=self.handle_kind_selection_change,
            )
            .classes("flex-1")
            .bind_value(self.context, target_name="kind")
            .bind_enabled_from(self.context, "allow_kind_change")
        )

    async def handle_kind_selection_change(self, e: ValueChangeEventArguments) -> None:
        """Callback triggered when the kind selection changes."""
        # The kind is already bound to the "kind" attribute of the context obj-
        # etc, but additional change-handling logic can be added to this method
        self.help_section.refresh()
        return None

    async def done_callback(self, e: ClickEventArguments) -> None:
        """Callback wired to the Done button click event"""
        return self.submit(self.context.model)

    def namespace_input(
        self, label: str = "Namespace", *, enabled: bool = False, hidden: bool = False
    ) -> None:
        """An input for the namespace in which the manifest exists/should be
        created. Disabled and hidden by default.
        """
        ns_input = (
            ui.input(label=label)
            .classes("flex-1")
            .bind_value(self.context.model["metadata"], target_name="namespace")
        )
        ns_input.enabled = enabled
        ns_input.visible = hidden

    @classmethod
    async def create(cls, *args: Any, **kwargs: Any) -> Self:
        """Async factory method."""
        dialog = cls(*args, **kwargs)
        return dialog

    @classmethod
    async def click(
        cls, e: ClickEventArguments, ctx: EditorContext, *, title: str = "Manifest Editor"
    ) -> MaybeDict:
        """Callback method for a click event meant to open the dialog, e.g.,
        from a button.

        This method implements the async await dialog pattern that returns a
        result object from a `submit()` method called elsewhere in the dialog
        logic. This pattern can be used directly in pages that need to use a
        dialog.
        """
        result: MaybeDict = await cls(ctx=ctx, title=title)

        if result is not None and ctx.callback is not None:
            callback_result: MaybeDict | Awaitable[MaybeDict] = ctx.callback(result)
            if isinstance(callback_result, Awaitable):
                return await callback_result
            else:
                return callback_result
        else:
            return result


class NewStepEditorDialog(EditorDialog):
    """An editor dialog for adding steps to a new campaign."""

    validation_handlers: list[str] = ["spec_model_validator"]
    group_option: ui.dropdown_button

    def ribbon(self) -> None:
        super().ribbon()
        self.context.kind = "step"
        self.context.allow_kind_change = False
        if not self.context.model["spec"]:
            self.context.model["spec"] = {
                "bps": {"pipeline_yaml": "${DRP_PIPE_DIR}/path/to/file.yaml#anchor"},
                "groups": None,
            }
        with ui.dropdown_button("Grouping", auto_close=True) as self.group_option:
            self.group_option.tooltip("Apply a grouping template spec to the Step")
            ui.item("No Grouping", on_click=self.set_group_config).props("id=grouping_none")
            ui.item("Fixed-Value Grouping", on_click=self.set_group_config).props("id=grouping_fixed")
            ui.item("Query Grouping", on_click=self.set_group_config).props("id=grouping_query")

    async def set_group_config(self, data: ClickEventArguments) -> None:
        """Patches the step's group configuration with a template config based
        on the group option selection.

        Note: This is a destructive operation and will replace the entire
        current grouping configuration with a new, empty, template config.
        """
        group_config: dict | None
        match data.sender._props:
            case {"id": "grouping_none"}:
                group_config = None
            case {"id": "grouping_fixed"}:
                group_config = {
                    "split_by": "values",
                    "dimension": None,
                    "values": [],
                }
            case {"id": "grouping_query"}:
                group_config = {
                    "split_by": "query",
                    "dataset": None,
                    "dimension": None,
                    "min_groups": 1,
                    "max_size": 0,
                }
            case _:
                raise RuntimeError("no such grouping config option")

        # apply the selected grouping template to the editor
        # validate that the editor is in a valid YAML state so patches can be
        # made
        try:
            temp_spec = yaml.safe_load(self.editor.value)
            if temp_spec is None:
                temp_spec = {}
            temp_spec["groups"] = group_config
            self.editor.set_value(yaml.safe_dump(temp_spec))
            self.editor.update()
        except yaml.YAMLError:
            self.context.valid = False
            self.error_log.push(
                "Spec contains invalid YAML, please correct before applying a grouping template."
            )

    def spec_model_validator(self) -> None:
        """Validates an editor spec against a pydantic model. If invalid,
        constructs as helpful an error message as possible including field
        description and examples.

        Raises
        ------
        SpecValidationError
            If validation does not succeed.
        """
        # The kind of manifest it is determines the spec we'll use to validate
        if self.context.kind is None:
            raise SpecValidationError("Step kind is not set correctly.")
        elif self.context.kind == "breakpoint":
            return None
        try:
            kind_model = KIND_TO_SPEC[self.context.kind]
            _ = kind_model.model_validate(self.context.model["spec"])
        except ValidationError as e:
            self.error_log.push(e, classes="text-negative")
            raise SpecValidationError("This is not a good spec.")


class NewManifestEditorDialog(EditorDialog):
    """An editor for editing new manifests for a new or existing campaign."""

    validation_handlers: list[str] = ["spec_model_validator"]

    def ribbon(self) -> None:
        super().ribbon()
        self.kind_selector.set_options(
            [kind for kind in set(self.kind_selector.options).difference({"step"})]
        )
        ui.button("Apply Template", icon="settings_suggest", on_click=self.handle_apply_template).props(
            "fab outline"
        )

    def handle_apply_template(self) -> None:
        """Applies a template spec to the editor based on the selected manifest
        kind. If available, the first provided field example is used to build
        the template, otherwise a default value is used.
        """
        if self.context.kind is None:
            return None
        template = {}
        kind_model = KIND_TO_SPEC[self.context.kind]
        for field_name, field_info in kind_model.model_fields.items():
            if field_info.examples:
                field_example = field_info.examples[0]
                if isinstance(field_example, dict):
                    template[field_name] = field_example.get(field_name, field_example)
                else:
                    template[field_name] = field_example
            else:
                template[field_name] = field_info.get_default(call_default_factory=True)
        self.editor.set_value(yaml.safe_dump(template))
        self.editor.update()

    async def handle_kind_selection_change(self, e: ValueChangeEventArguments) -> None:
        """Callback triggered when the kind selection changes."""
        self.context.model["kind"] = e.value
        self.help_section.refresh()

    def spec_model_validator(self) -> None:
        """Validates an editor spec against a pydantic model. If invalid,
        constructs as helpful an error message as possible including field
        description and examples.

        Raises
        ------
        SpecValidationError
            If validation does not succeed.
        """
        # The kind of manifest it is determines the spec we'll use to validate
        try:
            # Pop the manifest "kind" from metadata to document root
            if self.context.kind is not None:
                self.context.model["kind"] = self.context.kind
            else:
                raise SpecValidationError("A manifest Kind is not set.")
            kind_model = KIND_TO_SPEC[self.context.kind]
            _ = kind_model.model_validate(self.context.model["spec"])
        except ValidationError as e:
            self.error_log.push(e, classes="text-negative")
            raise SpecValidationError("This is not a good spec.")


class AddStepEditorDialog(NewStepEditorDialog):
    """A dialog for editing steps being added to an existing campaign."""

    ancestor_node_select: ui.select

    def ribbon(self) -> None:
        super().ribbon()
        self.kind_selector.set_options(["step", "breakpoint"])
        self.context.kind = "step"
        self.context.allow_kind_change = True
        self.ancestor_node_select = (
            ui.select(options=[], label="Insert After Step...")
            .classes("flex-1")
            .bind_value(self.context.model["metadata"], target_name="ancestor")
        )
        # TODO if a page wants to fix the ancestor node, use it now instead of
        # looking through the graph. This might be as straightfwd as seeding
        # the context model metadata with the ancestor id and checking it here
        self.determine_candidate_ancestors()
        self.context.model["spec"] = {
            "bps": {"pipeline_yaml": "${DRP_PIPE_DIR}/path/to/file.yaml#anchor"},
            "groups": None,
        }

    def determine_candidate_ancestors(self) -> None:
        """method to update the candidate ancestors drop down options
        based on nodes known to the page's graph. Note that the "END"
        node is not a candidate ancestor for a new step.
        """
        if "graph" not in self.context.page.model:
            ui.notify("Page model does not have a graph", type="negative")
            return None
        candidate_ancestors = set(self.context.page.model["graph"].nodes).difference({"END.1"})
        candidate_ancestor_mapping = {
            n["id"]: f"""{n["name"]} v{n["version"]}"""
            for n in self.context.page.model["nodes"]
            if f"""{n["name"]}.{n["version"]}""" in candidate_ancestors
        }
        self.ancestor_node_select.set_options(candidate_ancestor_mapping)

    async def handle_kind_selection_change(self, e: ValueChangeEventArguments) -> None:
        """Callback triggered when the kind selection changes."""
        # The kind is already bound to the "kind" attribute of the context obj-
        # etc, but additional change-handling logic can be added to this method
        self.context.model["metadata"]["kind"] = e.value
        self.context.kind = e.value

        # NOTE this callback can fire before an editor is created, e.g., when
        # a default kind is set in the `ribbon` method, so we protect against
        # an AttributeError in that case
        try:
            if e.value == "breakpoint":
                self.context.model["spec"] = {}
                self.context.readonly = True
                self.group_option.disable()
                self.context.valid = True
                self.editor.classes(add="opacity-0")
            elif e.value == "step":
                self.context.readonly = False
                self.group_option.enable()
                self.context.valid = None
                self.editor.classes(remove="opacity-0")
        except AttributeError:
            pass

        self.help_section.refresh()

    async def done_callback(self, event: ClickEventArguments) -> None:
        """Callback wired to the Done button click event"""
        try:
            if not self.context.valid:
                raise SpecValidationError("Editor must be validated.")
            if self.ancestor_node_select.value is None:
                raise SpecValidationError("Ancestor node must be set.")
            if self.context.model["metadata"]["name"] is None:
                raise SpecValidationError("A valid name must be set.")
        except SpecValidationError as e:
            ui.notify(e, type="negative")
            return None
        return self.submit(self.context.model)


class StepEditorDialog(NewStepEditorDialog):
    """Editor dialog for an existing step in a campaign"""

    def ribbon(self) -> None:
        super().ribbon()

        ui.chip(
            text="Read only",
            icon="edit_off",
            color="dark",
            text_color="white",
        ).classes("flex-0 self-center").bind_visibility_from(self.context, target_name="readonly").tooltip(
            "Nodes not in waiting state are read-only"
        )

        # Full editing capabilities allowed when the step is in waiting
        if self.context.readonly:
            self.group_option.disable()
            self.context.valid = True
            self.context.readonly = True
