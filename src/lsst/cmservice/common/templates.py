"""Module for classes and functions dealing with templates, especially those
used in the operation of a Scheduled Campaign.
"""

from collections import defaultdict, deque
from collections.abc import Mapping, MutableMapping, Sequence
from datetime import datetime, timedelta
from typing import Any, Literal, overload
from uuid import UUID, uuid5

from jinja2.exceptions import TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment
from yaml import YAMLError, safe_load

from lsst.cmservice.models.api.manifests import (
    CampaignManifest,
    EdgeManifest,
    ManifestModel,
    NodeManifest,
)
from lsst.cmservice.models.api.manifests import (
    Manifest as RequestManifest,
)
from lsst.cmservice.models.api.schedules import ScheduleConfiguration
from lsst.cmservice.models.db.campaigns import CampaignElement
from lsst.cmservice.models.db.schedules import ManifestTemplateBase
from lsst.cmservice.models.enums import DEFAULT_NAMESPACE, ManifestKind
from lsst.cmservice.models.lib.jinja import FILTERS
from lsst.cmservice.models.lib.timestamp import now_utc
from lsst.cmservice.models.lib.transformer import manifest_to_orm


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


async def prepare_orm_from_manifest(manifest: dict, namespace: UUID | None = None) -> CampaignElement:
    """Given a dictionary representation of a campaign element manifest,
    create and return an ORM object for that manifest.

    This function implements some of the same business logic as found in the
    creation REST API for a given manifest kind, but always in the context of
    creating objects for a new campaign -- so versions are always 1, there are
    no pre-checks for existing objects, etc.

    After the business logic is applied to the manifest request, we get an ORM
    from a transformer

    Parameters
    ----------
    manifest: Mapping
        A campaign element manifest as a python dict, as one loaded from YAML
        or JSON.

    namespace: UUID | None
        The namespace in which the element should exist. If not None, the UUID
        is added to the ORM object's metadata.

    Raises
    ------
    RuntimeError
        If an ORM object can't be prepared from the given inputs, e.g., an
        edge manifest without a namespace.
    """
    # One assumption this function can make is that it is only ever preparing
    # VERSION 1 objects for a NEW CAMPAIGN, which simplifies the service-layer
    # logic of generating Node and Edge ORM objects.

    api_request_mapping: defaultdict[str, type[RequestManifest]] = defaultdict(
        lambda: ManifestModel,
        campaign=CampaignManifest,
        node=NodeManifest,
        edge=EdgeManifest,
    )

    # Using the dict manifest, apply business logic to it and build a request
    # model object from it. This is notably similar to what FastAPI is doing
    # with request bodies in our POST routes.
    if namespace is not None:
        manifest["metadata"] |= {"namespace": str(namespace)}

    match manifest["kind"]:
        case "edge":
            if namespace is None:
                raise RuntimeError("Can't create an edge without a namespace")

            # in an edge, the adjacencies may be specified as a uuid string,
            # an unversioned name, or a versioned name.
            for key in ["source", "target"]:
                node = manifest["spec"][key]
                try:
                    _ = UUID(node)
                    # this is fine, do nothing else
                except ValueError:
                    # make sure the node is always version 1
                    node_name = node.split(".")[0]
                    adjacency = uuid5(namespace, f"{node_name}.1")
                    manifest["spec"][key] = str(adjacency)

        case _:
            manifest["metadata"]["version"] = 1

    manifest_request = api_request_mapping[manifest["kind"]].model_validate(manifest)
    orm = manifest_to_orm(manifest_request)
    return orm


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
    # campaign -> manifests -> nodes -> edges
    rendered_manifests: deque[Any] = deque(maxlen=len(templates))
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
