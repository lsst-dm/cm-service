"""Module for classes and functions dealing with templates, especially those
used in the operation of a Scheduled Campaign.
"""

from collections import deque
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid5

from jinja2.exceptions import TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment
from yaml import YAMLError, safe_load

from lsst.cmservice.models.db.campaigns import Campaign, Edge, Manifest, Node
from lsst.cmservice.models.db.schedules import ManifestTemplate
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE

type CampaignElement = Campaign | Node | Edge | Manifest
"""A type representing the union of all available campaign element objects"""


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


def as_exposure(value: datetime, exposure: int = 0) -> str:
    return f"{value:%Y%m%d}{exposure:05d}"


def compile_user_expressions(expressions: MutableMapping) -> dict[str, Any]:
    """Compiles user template expressions in a dedicated sandbox environment
    with a whitelisted set of Python modules available as globals. Each
    expressed value is cast as a string before being returned as a mapping
    of expression name to expression result.
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


async def prepare_orm_from_manifest(manifest: dict, namespace: UUID | None = None) -> CampaignElement:
    """Given a dictionary representation of a campaign element manifest,
    create and return an ORM object for that manifest.

    This is a service-layer function that should be added to lib for reuse.

    Parameters
    ----------
    manifest: Mapping
        A campaign element manifest as a python dict, as one loaded from YAML
        or JSON.

    namespace: UUID | None
        The namespace in which the element should exist. If not None, the UUID
        is added to the ORM object's metadata.
    """
    # One assumption this function can make is that it is only ever preparing
    # VERSION 1 objects for a NEW CAMPAIGN, which simplifies the service-layer
    # logic of generating Node and Edge ORM objects.
    orm: CampaignElement

    if namespace is not None:
        manifest |= {"namespace": namespace}

    match manifest["kind"]:
        case "campaign":
            orm = Campaign.model_validate(manifest)
        case "node":
            orm = Node.model_validate(manifest)
        case "edge":
            if namespace is None:
                raise RuntimeError("Can't prepare an Edge ORM without a namespace")
            source_node = f"""{manifest["spec"]["source"]}.1"""
            target_node = f"""{manifest["spec"]["target"]}.1"""

            orm = Edge.model_validate(
                manifest
                | {
                    "id": uuid5(namespace, f"{source_node}->{target_node}"),
                    "source": uuid5(namespace, source_node),
                    "target": uuid5(namespace, target_node),
                },
            )
        case _:
            orm = Manifest.model_validate(
                manifest
                | {
                    "version": 1,
                },
            )

    return orm


# OR: why destructure the Schedule object into individual arguments to these
# different functions? Just use it as a context object, detaching it from the
# session as necessary.
async def build_sandbox_and_render_templates(
    expressions: dict,
    templates: list[ManifestTemplate],
) -> Sequence[CampaignElement]:
    """Given a set of expressions for the sandbox environment, create an
    environment and render the collection of templates.

    Manifest templates associated with the schedule are stored as TEXT
    documents and used with a jinja template environment. The resulting render-
    ed template must be a valid YAML document for a campaign Manifest. The
    collection of rendered and parsed/loaded manifests is returned as a
    sequence of ORM objects.
    """
    # . expressions = schedule.expressions
    # . templates = schedule.templates
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

    # put the manifest templates in loose order in the result deque
    # campaign -> manifests -> nodes -> edges
    rendered_manifests: deque[Any] = deque(maxlen=len(templates))
    rendered_edges: list[dict] = []

    for template in templates:
        try:
            rendered_template = sandbox.from_string(template.manifest).render()
            template_dict: dict = safe_load(rendered_template)
        except TemplateError:
            # jinja error
            ...
        except YAMLError:
            # parsing error
            ...
        match template_dict["kind"]:
            case "campaign":
                rendered_manifests.appendleft(template_dict)
            case "edge":
                rendered_edges.append(template_dict)
            case _:
                rendered_manifests.append(template_dict)

    # Add the accumulated edge manifests to the end of the deque
    rendered_manifests.extend(rendered_edges)

    # Work through the deque to create Manifest ORM objects from each rendered
    # template, populating the campaign namespace for each
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
