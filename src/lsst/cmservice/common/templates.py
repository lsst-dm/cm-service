"""Module for classes and functions dealing with templates, especially those
used in the operation of a Scheduled Campaign.
"""

from collections import deque
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Literal, overload

from jinja2.exceptions import TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment
from yaml import YAMLError, safe_load

from lsst.cmservice.models.api.primitives import STEP_MANIFEST_TEMPLATE
from lsst.cmservice.models.api.schedules import ScheduleConfiguration
from lsst.cmservice.models.db.campaigns import CampaignElement
from lsst.cmservice.models.db.schedules import ManifestTemplateBase
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE, ManifestKind
from lsst.cmservice.models.lib.jinja import FILTERS
from lsst.cmservice.models.lib.timestamp import element_time, now_utc
from lsst.cmservice.models.lib.transformer import prepare_orm_from_manifest


class ManifestRenderingError(Exception): ...


def compile_user_expressions(expressions: MutableMapping[str, str]) -> dict[str, Any]:
    """Compiles user template expressions in a dedicated sandbox environment
    with a whitelisted set of Python modules available as globals.

    Returns
    -------
    dict[str, Any]
        A mapping of each expression name to its compiled value.
    """
    whitelist_modules: Mapping[str, type] = {
        "datetime": datetime,
        "timedelta": timedelta,
    }
    sandbox = ImmutableSandboxedEnvironment()
    sandbox.globals.update(whitelist_modules)

    # TODO exception handling here, should the expression blow up
    # Compile and evaluate the user expression in the sandbox environment
    compiled_expressions = {
        name: sandbox.compile_expression(expression)() for name, expression in expressions.items()
    }
    return compiled_expressions


@overload
async def build_sandbox_and_render_templates[T: ManifestTemplateBase](
    context: ScheduleConfiguration,
    templates: Sequence[T],
    *,
    as_orm: Literal[True],
) -> Sequence[CampaignElement]: ...


@overload
async def build_sandbox_and_render_templates[T: ManifestTemplateBase](
    context: ScheduleConfiguration,
    templates: Sequence[T],
    *,
    as_orm: Literal[False],
) -> Sequence[dict]: ...


@overload
async def build_sandbox_and_render_templates[T: ManifestTemplateBase](
    context: ScheduleConfiguration,
    templates: Sequence[T],
) -> Sequence[CampaignElement]: ...


async def build_sandbox_and_render_templates[T: ManifestTemplateBase](
    context: ScheduleConfiguration,
    templates: Sequence[T],
    *,
    as_orm: bool = True,
) -> Sequence[Any]:
    """Given a set of expressions for the sandbox environment, create an
    environment and render the collection of templates.

    Manifest templates associated with the schedule are stored as TEXT
    documents and used with a jinja template environment. The resulting render-
    ed template must be a valid YAML document for a campaign Manifest. The
    collection of rendered and parsed/loaded manifests is returned as a
    sequence of ORM objects.

    Parameters
    ----------
    as_orm: bool
        If True (default), the return value is a sequence of ORM objects
        created from the rendered manifest templates; if False, the raw
        rendered strings are returned instead.
    """
    compiled_expressions = compile_user_expressions(context.expressions)

    sandbox = ImmutableSandboxedEnvironment(
        variable_start_string="{{",
        variable_end_string="}}",
        newline_sequence="\n",
        keep_trailing_newline=True,
        cache_size=0,
    )
    sandbox.globals = compiled_expressions
    sandbox.filters |= FILTERS

    # put the manifest templates in loose order in the result deque
    # campaign -> start/end -> manifests/nodes -> edges
    rendered_manifests: deque[Any] = deque(maxlen=len(templates) + 2)
    rendered_edges: list[dict] = []

    for template in templates:
        try:
            rendered_template = sandbox.from_string(template.manifest).render()
            template_dict: dict = safe_load(rendered_template)
        except TemplateError as e:
            raise ManifestRenderingError("Could not render template; check variable and filter names.") from e
        except YAMLError as e:
            raise ManifestRenderingError(
                "Could not load rendered template as YAML, check source template structure."
            ) from e

        match template.kind:
            case ManifestKind.campaign:
                # Set the campaign *name* according to the schedule config
                campaign_name_nonce = now_utc().strftime(context.name_format)
                campaign_name = f"{template_dict['metadata']['name']}_{campaign_name_nonce}"
                template_dict["metadata"]["name"] = campaign_name
                rendered_manifests.appendleft(template_dict)

                # Start/End Nodes
                start_node = STEP_MANIFEST_TEMPLATE | {
                    "metadata": {"name": "START", "kind": "start", "crtime": element_time()}
                }
                end_node = STEP_MANIFEST_TEMPLATE | {
                    "metadata": {"name": "END", "kind": "end", "crtime": element_time()}
                }
                rendered_manifests.append(start_node)
                rendered_manifests.append(end_node)
            case ManifestKind.edge:
                rendered_edges.append(template_dict)
            case _:
                rendered_manifests.append(template_dict)

    # Add the accumulated edge manifests to the end of the deque
    rendered_manifests.extend(rendered_edges)

    # Work through the deque to create Manifest ORM objects from each rendered
    # template, populating the campaign namespace for each
    if as_orm:
        current_namespace = DEFAULT_NAMESPACE
        for _ in range(len(rendered_manifests)):
            _manifest: dict[str, Any] = rendered_manifests.popleft()
            _orm = await prepare_orm_from_manifest(
                _manifest,
                current_namespace,
            )
            rendered_manifests.append(_orm)
            # set the current namespace after a campaign ORM has been prepared
            if _manifest["kind"] == "campaign":
                current_namespace = _orm.id

    return rendered_manifests
