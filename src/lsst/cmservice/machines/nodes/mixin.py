from os.path import expandvars
from typing import TYPE_CHECKING

import yaml
from anyio import Path
from jinja2 import Environment, PackageLoader
from sqlmodel.ext.asyncio.session import AsyncSession
from transitions import EventData

from ...common.enums import ManifestKind
from ...config import config
from ...db.campaigns_v2 import Node
from .. import lib


class ActionNodeMixin:
    """Mixin class providing methods relating to ACTIONS a Node may take,
    especially those impacting IO.

    Generally, a Node using this mixin will have attributes describing an art-
    ifact path and a set of Jinja2 Templates necessary to render as output
    artifacts during its "prepare" trigger.

    Attributes
    ----------
    templates: list[tuple[str, ...]]
        A list of tuples. Each tuple pairs a Jinja2 template name with
        a filename. The specified template will be rendered as the specified
        filename.
    """

    session: AsyncSession
    db_model: Node
    templates: list[tuple[str, ...]]

    async def get_artifact_path(self, event: EventData) -> Path | None:
        """Determine filesystem location as a `pathlib` or `anyio` ``Path``
        object, returning ``None`` if the path cannot be determined.
        """
        if self.session is None:
            return None
        if self.db_model is None:
            return None
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)

        fallback_configuration = {"lsst": {"artifact_path": expandvars(config.bps.artifact_path)}}
        config_chain = await lib.assemble_config_chain(
            self.session, self.db_model, manifest_kind=ManifestKind.lsst, extra=[fallback_configuration]
        )
        artifact_path = config_chain["lsst"]["artifact_path"]
        return Path(artifact_path) / str(self.db_model.namespace)

    async def render_action_templates(self, event: EventData) -> None:
        """Render the set of templates associated with this Node via the
        `templates` attribute, using the Node's configuration chain as a
        context environment.
        """
        if (artifact_path := await self.get_artifact_path(event)) is None:
            raise RuntimeError("Unable to determine artifact path.")

        # Get the yaml template using package lookup and wire in any custom
        # template filters
        action_template_environment = Environment(loader=PackageLoader("lsst.cmservice"))
        action_template_environment.filters["toyaml"] = yaml.dump
        # TODO build config chain map
        action_template_context = {}

        for template, filename in self.templates:
            output_path = await (artifact_path / filename).resolve()
            action_template = action_template_environment.get_template(template)
            try:
                rendered_output = action_template.render(action_template_context)
                await output_path.write_text(rendered_output)
            except yaml.YAMLError as yaml_error:
                raise yaml.YAMLError(f"Error rendering YAML template; threw {yaml_error}")
