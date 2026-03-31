"""Module for classes and functions dealing with templates, especially those
used in the operation of a Scheduled Campaign.
"""

from collections import deque
from collections.abc import MutableMapping, MutableSequence
from datetime import datetime, timedelta
from typing import Any, Literal

from jinja2.sandbox import ImmutableSandboxedEnvironment


# Jinja Filter functions
# All filter functions should take at least one positional `value` argument.
def as_lsst_version(value: datetime, format: Literal["weekly", "daily"] = "weekly") -> str:
    """Given a datetime input, construct a "weekly" LSST version."""
    match format:
        case "weekly":
            return f"{value:w_%G_%V}"
        case "daily":
            return f"{value:d_%Y_%m_%d}"


def as_obs_day(value: datetime) -> str:
    """Given a datetime input, construct an "obs_day" format"""
    return f"{value:%Y%m%d}"


def as_exposure(value: datetime, exposure=0) -> str:
    return f"{value:%Y%m%d}{exposure:05d}"


def compile_user_expressions(expressions: MutableMapping) -> dict[str, Any]:
    """Compiles user template expressions in a dedicated sandbox environment
    with a whitelisted set of Python modules available as globals. Each
    expressed value is cast as a string before being returned as a mapping
    of expression name to expression result.
    """
    whitelist_modules = {
        "datetime": datetime,
        "timedelta": timedelta,
    }
    sandbox = ImmutableSandboxedEnvironment()
    sandbox.globals = whitelist_modules

    # TODO exception handling here, should the expression blow up
    # Compile and evaluate the user expression in the sandbox environment
    compiled_expressions = {
        name: sandbox.compile_expression(expression)() for name, expression in expressions.items()
    }
    return compiled_expressions


# OR: why destructure the Schedule object into individual arguments to these
# different functions? Just use it as a context object, detaching it from the
# session as necessary.
async def build_sandbox_and_render_templates(expressions: dict, templates: list[str]) -> MutableSequence[str]:
    """Given a set of expressions for the sandbox environment, create an
    environment and render the collection of templates.
    """
    # . expressions = schedule.expressions
    # . templates = schedule.templates
    rendered_templates = deque(maxlen=len(templates))
    compiled_expressions = compile_user_expressions(expressions)

    sandbox = ImmutableSandboxedEnvironment(
        variable_start_string="{{",
        variable_end_string="}}",
        newline_sequence="\n",
        keep_trailing_newline=True,
        cache_size=0,
    )
    sandbox.globals = compiled_expressions
    sandbox.filters |= {
        "as_lsst_version": as_lsst_version,
        "as_obs_day": as_obs_day,
        "as_exposure": as_exposure,
    }

    for template in templates:
        # put the manifest templates in loose order in the result deque
        # campaign -> manifests -> nodes -> edges
        # this just means that (1) campaign should be added to the left
        # and then edges are added to the right
        # nodes and manifests can be put anywhere else.
        rendered_template = sandbox.from_string(template).render()
        rendered_templates.append(rendered_template)

    return rendered_templates
