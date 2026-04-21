"""Module for an expression-editor dialog, used for setting up a Scheduled
Campaign's jinja variables.
"""

from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING

from nicegui import ui
from nicegui.events import ClickEventArguments, ValueChangeEventArguments

from lsst.cmservice.models.lib.parsers import as_snake_case


@dataclass
class ExpressionEditorModel:
    """Data model for the expression editor dialog.

    Attributes
    ----------
    expressions: dict[str, str]
        A mapping of variable names to their corresponding Python expression.
    """

    expressions: dict[str, str] = field(default_factory=dict)


class ExpressionEditorDialog(ui.dialog):
    def __init__(
        self, *, dialog_title: str = "Template Expressions", with_expressions: dict[str, str] = {}
    ) -> None:
        super().__init__()
        self.model = ExpressionEditorModel(expressions=with_expressions)
        self.dialog_title = dialog_title
        self.dialog_layout()

    def dialog_layout(self) -> None:
        with self, ui.card().classes("w-full"):
            ui.label(self.dialog_title).classes("font-bold text-3xl")
            with ui.row().classes("flex w-full items-center"):
                self.variable_name_input = (
                    ui.input(label="Variable Name", on_change=self.validate_variable_name)
                    .classes("flex-1")
                    .props("clearable debounce=1000")
                )
                self.expression_input = (
                    ui.input(label="Expression")
                    .classes("font-mono color-gray-500w flex-1")
                    .props("clearable debounce=1000")
                )
                ui.button(icon="add", on_click=self.handle_add_expression, color="accent").props(
                    "fab-mini"
                ).tooltip("Add")

            ui.separator()
            with ui.column().classes("w-full") as self.expressions_list:
                self.render_expressions_list()

            ui.separator().classes("mb-0")
            with ui.expansion("Help").classes("w-full m-0 p-0"):
                ui.markdown(
                    """
                    - Variables you create here can be used in your Campaign's manifest as jinja template variables, e.g. `{{ my_variable }}`.
                    - Variables should always be named using valid Python variable naming conventions, e.g. `my_variable`.
                    - Expressions should be valid Python expressions that can be evaluated with `eval()`.
                    - Example: `datetime.now() - timedelta(days=7)` to represent a variable that evaluates to the date 7 days ago.
                    - Some custom Jinja filters are available for use in expressions, including:
                        - `as_exposure`: datetime as a `YYYYMMDD#####` string
                        - `as_obs_day`: datetime as a `YYYYMMDD` string
                        - `as_lsst_version`: datetime as a weekly or daily LSST version string
                    """  # noqa: E501
                ).classes("max-h-64 overflow-auto")

            ui.separator()
            with ui.card_actions().classes("w-full align-left"):
                with ui.row().classes("flex w-full"):
                    ui.button("Save", color="positive", on_click=lambda: self.submit(self.model.expressions))
                    ui.button("Cancel", color="negative", on_click=lambda: self.submit(None))

    @ui.refreshable_method
    def render_expressions_list(self) -> None:
        """Refreshable method to update the displayed list of expressions based
        on the current state of the model.
        """
        with ui.list().classes("w-full"):
            for k, v in self.model.expressions.items():
                chip_callback = partial(self.handle_chip_click, variable=k, expression=v)
                delete_callback = partial(self.handle_remove_expression, variable_name=k)
                with ui.item():
                    ui.chip(f"{k} = {v}", on_click=chip_callback).classes("w-full text-white").props(
                        "clickable"
                    )
                    ui.button(icon="delete_forever", color="orange", on_click=delete_callback).props(
                        "flat"
                    ).tooltip("Delete expression")

    async def handle_add_expression(self, e: ClickEventArguments) -> None:
        """Callback for adding a new expression to the list and model."""
        self.model.expressions[self.variable_name_input.value] = self.expression_input.value
        self.variable_name_input.set_value("")
        self.expression_input.set_value("")
        await self.render_expressions_list.refresh()

    async def handle_remove_expression(self, e: ClickEventArguments, *, variable_name: str) -> None:
        """Callback for removing an expression from the list and model."""
        if TYPE_CHECKING:
            assert isinstance(e.sender, ui.button)
        if variable_name in self.model.expressions:
            del self.model.expressions[variable_name]
            await self.render_expressions_list.refresh()

    async def handle_chip_click(self, e: ClickEventArguments, *, variable: str, expression: str) -> None:
        """Callback for when an expression chip is clicked, to populate the
        input fields for easy editing.
        """
        self.variable_name_input.set_value(variable)
        self.expression_input.set_value(expression)

    async def validate_variable_name(self, e: ValueChangeEventArguments) -> None:
        """Ensure the variable name input is always in snake_case and does not
        contain invalid characters.
        """
        if TYPE_CHECKING:
            assert isinstance(e.sender, ui.input)
        if e.value == e.previous_value:
            return None
        else:
            e.sender.value = as_snake_case(e.sender.value)
