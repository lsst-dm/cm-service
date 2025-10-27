from __future__ import annotations

from collections.abc import AsyncGenerator
from os.path import expandvars
from typing import TYPE_CHECKING, Any

import yaml
from anyio import Path, TemporaryDirectory
from jinja2 import Environment, PackageLoader, Template
from sqlalchemy.exc import MissingGreenlet, NoResultFound
from sqlmodel import desc, or_, select
from transitions import EventData

from ...common.enums import DEFAULT_NAMESPACE, ManifestKind, StatusEnum
from ...common.errors import CMNoSuchManifestError
from ...common.htcondor import HTCondorManager
from ...common.launchers import LauncherCheckResponse
from ...common.logging import LOGGER
from ...config import config
from ...db.campaigns_v2 import Manifest, Node
from ...models.manifest import LibraryManifest
from .. import lib
from .abc import ActionMixIn, LaunchMixIn, MixIn

logger = LOGGER.bind(module=__name__)


class NodeMixIn(MixIn):
    """Mixin Methods for a Stateful Model representing any kind of Node in a
    campaign graph.
    """

    # TODO if no more functionality is added in this mixin, just promote this
    # method into the NodeMachine class.
    async def get_manifest[T: LibraryManifest](
        self, manifest_kind: ManifestKind, manifest_type: type[T]
    ) -> T:
        """Fetches the appropriate Manifest for the Campaign. The newest
        manifest of the specified Kind is retrieved from the campaign or
        the library namespace, and an object of `type[manifest_type]` is
        created and returned.

        Notes
        -----
        The Manifest instance returned by this method is not an ORM model and
        cannot be used to manipulate the manifest in the database. The fetched
        ORM object is expunged from the session.

        Raises
        ------
        CMNoSuchManifestError
            Raised when the Node attempts to load a Manifest that cannot be
            found in the Campaign or the Library.
        """
        # Look in the campaign namespace for the most recent manifest,
        # falling back to the default namespace if one is not found.
        s = (
            select(Manifest)
            .where(Manifest.kind == manifest_kind)
            .where(
                or_(Manifest.namespace == self.db_model.namespace, Manifest.namespace == DEFAULT_NAMESPACE)
            )
            .order_by(desc(Manifest.version))
            .limit(1)
        )
        try:
            manifest = (await self.session.exec(s)).one()
            self.session.expunge(manifest)
        except NoResultFound:
            msg = f"A required manifest was not found in the database: {manifest_kind}"
            raise CMNoSuchManifestError(msg)

        o = manifest_type(**manifest.model_dump())
        o.metadata_.version = manifest.version
        return o


class FilesystemActionMixin(ActionMixIn):
    """Mixin class providing methods for Action nodes.

    An Action Node provides a set of methods used by Nodes that need to perform
    operations in an environment external to the CM Service. This includes
    creating filesystem objects in mounted systems, rendering Jinja templates,
    etc.

    This mixin adds attributes to the class with which it is mixed.

    Attributes
    ----------
    artifact_path: Path
        A `pathlib.Path` or equivalent object representing the location to
        which this Node will render its templates. This path may also be
        referenced within templates to specify the path component of emergent
        objects like log files.

    templates: list[tuple[str, ...]]
        A list of Jinja templates that are available in the ``lsst.cmservice``
        package. Each template is specified as a tuple of the template name and
        the name of the target file to which the template will be rendered.

    command_templates: list[str]
        A list of special jinja template strings that represents the executable
        command(s) that a Bash script should execute. These are the core exec-
        utive payload of the Node, such as a "bps submit" or "butler" command.

    configuration_chain: dict[str, ChainMap]
        A mapping of kinds of Manifests to a ChainMap lookup dictionary.

    Notes
    -----
    While this mixin is purpose-built for filesystem operations, these features
    have been modularized to better support future implementations of non-file-
    system operations, such as rendering templates to an object store, etc.
    """

    async def get_artifact_path(self, event: EventData) -> None:
        """Determine and create node-specific working directory as an
        ``anyio.Path`` instance.

        This method populates the `artifact_path` instance attribute and must
        be called after the `assemble_config_chain` method.
        """
        if TYPE_CHECKING:
            assert isinstance(self.db_model, Node)

        if not hasattr(self, "configuration_chain"):
            raise RuntimeError("Missing configuration chain for active node")

        # If the node's metadata has an artifact path specified, we use that
        # as a parent path, otherwise we use the campaign path
        lsst_artifact_path = self.configuration_chain["lsst"]["artifact_path"]

        # Use the name of the node's related campaign if it is available,
        # otherwise fall back to the campaign's id. The MissingGreenlet is for
        # cases where a lazy relationship lookup is invalid because it's
        # attempted outside an async session context (some tests may invoke
        # this case depending on how the Node was initially loaded)
        try:
            campaign_name = self.db_model.campaign.name
        except (AttributeError, MissingGreenlet):
            campaign_name = str(self.db_model.namespace)
        campaign_artifact_path = await (Path(lsst_artifact_path) / campaign_name).resolve()
        parent_path = Path(
            self.db_model.metadata_.get(
                "artifact_path",
                campaign_artifact_path,
            )
        )
        self.artifact_path = parent_path / self.db_model.kind.name / self.db_model.name
        await self.artifact_path.mkdir(parents=True, exist_ok=False)

    async def assemble_config_chain(self, event: EventData) -> None:
        """Constructs and sets the `configuration_chain` instance attribute."""
        # The fallback configuration is a baked-in set of defaults for some or
        # all configuration manifest kinds. These should be set and used
        # sparingly; runtime defaults are preferred over anything set here.
        fallback_configuration = {
            "lsst": {
                "artifact_path": expandvars(config.bps.artifact_path),
                "lsst_distrib_dir": expandvars(config.bps.lsst_distrib_dir),
                "lsst_version": expandvars(config.bps.lsst_version),
                "campaign": self.db_model.namespace.hex,
            },
            "bps": {
                "operator": "lsstsvc1",
            },
        }

        self.configuration_chain = await lib.assemble_config_chain(
            self.session, self.db_model, extra=fallback_configuration
        )

    async def render_action_templates(self, event: EventData) -> None:
        """Render the set of templates associated with this Node via the
        `templates` attribute, using the Node's configuration chain as a
        context environment. This method is a no-op if the Node does not have
        any templates defined.
        """

        if not hasattr(self, "templates") or self.templates is None:
            return None

        # Get the yaml template using package lookup and wire in any custom
        # template filters
        action_template_environment = Environment(loader=PackageLoader("lsst.cmservice"))
        action_template_environment.filters["toyaml"] = yaml.dump
        action_template_environment.filters["flatten_chainmap"] = lib.flatten_chainmap

        # Add any command_templates to the lsst config chain
        self.configuration_chain["lsst"] = self.configuration_chain["lsst"].new_child(
            {"command": self.command_templates}
        )

        # Each template is rendered in two passes. This supports the use of
        # *template strings* in variable values that may be rendered to a final
        # form in the second pass.
        for template, filename in self.templates:
            output_path = self.artifact_path / filename
            action_template = action_template_environment.get_template(template)
            try:
                intermediate_output = action_template.render(self.configuration_chain)
                rendered_output: str = Template(intermediate_output).render(self.configuration_chain)
                await output_path.write_text(rendered_output)
            except yaml.YAMLError as yaml_error:
                msg = f"Error rendering YAML template; threw {yaml_error}"
                raise yaml.YAMLError(msg)

    async def action_prepare(self, event: EventData) -> None:
        """Wrapper method for Action node preparation."""
        await self.assemble_config_chain(event)
        await self.get_artifact_path(event)

    async def get_artifact(self, event: EventData, artifact: Path | str) -> AsyncGenerator[Path]:
        """Copy an artifact from the provided path to a local temporary
        directory and return the Path to it.
        """
        remote_artifact = Path(artifact)
        if not await remote_artifact.exists():
            return
        async with TemporaryDirectory() as temp_dir:
            remote_bytes = await remote_artifact.read_bytes()
            local_artifact = Path(temp_dir) / remote_artifact.name
            await local_artifact.write_bytes(remote_bytes)
            yield local_artifact


class HTCondorLaunchMixin(LaunchMixIn):
    """Mixin class providing methods relating to Launch actions a Node may
    engage in. Examples include executing a script in a subprocess, as a worker
    node, or submitting a job to a WMS.

    Notes
    -----
    The mapping of variables referencing specific file types to attributes is

    wms_submission_path: The path to the file containing WMS submission
    instructions, e.g., a HTCondor Submit Description File.

    wms_event_log_path: The path to the file containing WMS execution logs,
    e.g., an HTCondor Job Event Log.

    wms_output_log_path: The path to the file to which the WMS should write the
    job's stdout and stderr.

    wms_executable_path: The path to the actual (usually Bash) script file to
    be executed by the launcher.
    """

    async def lsst_prepare(self, event: EventData) -> None:
        """Prepares launcher-specific LSST setup manifest used when rendering
        templates.
        """
        lsst_config: dict[str, Any] = {"launcher": []}
        lsst_config["launcher"].append("""export LSST_VERSION="{{ lsst.lsst_version }}" """)
        lsst_config["launcher"].append(
            """export LSST_DISTRIB_DIR="{{ lsst.lsst_distrib_dir.rstrip("/") }}" """
        )
        lsst_config["launcher"].append("""source ${LSST_DISTRIB_DIR}/${LSST_VERSION}/loadLSST.bash""")
        lsst_config["launcher"].append("""setup lsst_distrib""")
        self.configuration_chain["lsst"] = self.configuration_chain["lsst"].new_child(lsst_config)

    async def launch_prepare(self, event: EventData) -> None:
        """Prepares a configuration chain link for runtime Launch configs.

        Launch configurations are part of the WMS manifest chain.
        """

        if not hasattr(self, "templates") or self.templates is None:
            logger.warning("Cannot launch Node without templates", id=self.db_model.id)
            return None

        launch_executable_path: Path | None
        for template, filename in self.templates:
            if template == "wms_submit_sh.j2":
                launch_executable_path = await (self.artifact_path / filename).resolve()

        if launch_executable_path is None:
            raise RuntimeError("No WMS executable template known to Node.")

        # Add the HTcondor submission description template
        self.templates.append(
            ("htcondor_submit_description.j2", f"{self.db_model.name}.sub"),
        )

        # Prepare a Launch runtime config to add to the Node's config chain
        launch_config: dict[str, Any] = {}
        launch_config["working_directory"] = self.artifact_path
        launch_config["wms_executable_path"] = launch_executable_path
        launch_config["wms_event_log_path"] = launch_executable_path.with_suffix(".condorlog")
        launch_config["wms_submission_path"] = launch_executable_path.with_suffix(".sub")
        launch_config["wms_output_log_path"] = launch_executable_path.with_stem(
            f"{launch_executable_path.stem}_condorsub"
        ).with_suffix(".log")
        self.configuration_chain["wms"] = self.configuration_chain["wms"].new_child(launch_config)

        await self.lsst_prepare(event)

    async def launch(self, event: EventData) -> None:
        """Dispatch a launch event to the launch method associated with the
        node's WMS.

        If the ``config.mock_status`` parameter is set, this becomes a no-op
        dry-run.
        """
        if config.mock_status is not None:
            return

        self.launch_manager = HTCondorManager()

        # The wms_submission_path must be set in the configuration chain
        # by the `launch_prepare` method.
        wms_submission_path = self.configuration_chain["wms"].get("wms_submission_path")
        if wms_submission_path is None:
            msg = "No HTCondor submit description file known to node."
            raise RuntimeError(msg)

        # TODO the node should consider its own "weight" and determine
        # whether the job can be sent to the local universe for immediate
        # processing on a schedd or if it should go to the vanilla universe
        # for regular scheduling (which may involve needing to allocate nodes)
        cluster_id = await self.launch_manager.launch(submission_spec=wms_submission_path)
        self.db_model.metadata_["wms_job"] = cluster_id

    async def check(self, event: EventData) -> LauncherCheckResponse:
        """Calls the check method of the launch manager."""
        if config.mock_status is not None:
            return LauncherCheckResponse(success=(config.mock_status is StatusEnum.accepted))

        self.launch_manager = HTCondorManager()

        # The wms_event_log_path must be set in the configuration chain
        # by the `launch_prepare` method.
        wms_event_log_path = self.configuration_chain["wms"].get("wms_event_log_path")
        if wms_event_log_path is None:
            msg = "No HTCondor event log file known to node."
            raise RuntimeError(msg)

        # TODO reduce duplication & get this from "launcher.job_id" metadata
        cluster_id = self.db_model.metadata_.get("wms_job", 0)
        logger.debug("Checking HTCondor Job", id=str(self.db_model.id), cluster_id=cluster_id)
        return await self.launch_manager.check(cluster_id, wms_event_log_path)
