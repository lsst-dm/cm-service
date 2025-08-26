from os.path import expandvars
from typing import TYPE_CHECKING, Any

import yaml
from anyio import Path, open_process
from anyio.streams.text import TextReceiveStream
from jinja2 import Environment, PackageLoader, Template
from transitions import EventData

from ...common.errors import CMHTCondorSubmitError
from ...common.htcondor import build_htcondor_submit_environment
from ...config import config
from ...db.campaigns_v2 import Node
from .. import lib
from .abc import ActionMixIn, LaunchMixIn


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
        campaign_artifact_path = await (Path(lsst_artifact_path) / str(self.db_model.namespace)).resolve()
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
                "project": "DEFAULT",
            },
        }

        self.configuration_chain = await lib.assemble_config_chain(
            self.session, self.db_model, extra=fallback_configuration
        )

    async def render_action_templates(self, event: EventData) -> None:
        """Render the set of templates associated with this Node via the
        `templates` attribute, using the Node's configuration chain as a
        context environment.
        """

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
                raise yaml.YAMLError(f"Error rendering YAML template; threw {yaml_error}")

    async def action_prepare(self, event: EventData) -> None:
        """Wrapper method for Action node preparation."""
        await self.assemble_config_chain(event)
        await self.get_artifact_path(event)


class HTCondorLaunchMixin(LaunchMixIn):
    """Mixin class providing methods relating to Launch actions a Node may
    engage in. Examples include executing a script in a subprocess, as a worker
    node, or submitting a job to a WMS.

    Notes
    -----
    The mapping of variables referencing specific file types to attributes is

    htcondor_script_path -> wms_submission_path: The path to the file contain-
    ing WMS submission instructions, e.g., a HTCondor Submit Description File.

    htcondor_log -> wms_log_path: The path to the file containing WMS execution
    logs, e.g., an HTCondor Job Event Log.

    htcondor_sublog -> wms_submission_log_path: The path to the file to which
    the WMS should write its submission output and error logs.

    script_url -> wms_executable_path: The path to the actual (usually Bash)
    script file to be executed on a WMS.
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
        launch_config["wms_log_path"] = launch_executable_path.with_suffix(".condorlog")
        launch_config["wms_submission_path"] = launch_executable_path.with_suffix(".sub")
        launch_config["wms_submission_log_path"] = launch_executable_path.with_stem(
            f"{launch_executable_path.stem}_condorsub"
        ).with_suffix(".log")
        self.configuration_chain["wms"] = self.configuration_chain["wms"].new_child(launch_config)

        await self.lsst_prepare(event)

    async def launch(self, event: EventData) -> None:
        """Dispatch a launch event to the launch method associated with the
        node's WMS.
        """
        await self.submit_htcondor_job(event)

    async def submit_htcondor_job(self, event: EventData) -> None:
        """Submit a  `Script` to htcondor.

        If the ``config.mock_status`` parameter is set, this becomes a no-op
        dry-run.
        """
        if config.mock_status is not None:
            return

        try:
            wms_submission_path = self.configuration_chain["wms"].get("wms_submission_path")
            assert wms_submission_path is not None

            async with await open_process(
                [config.htcondor.condor_submit_bin, "-file", wms_submission_path],
                env=build_htcondor_submit_environment(),
            ) as condor_submit:
                if await condor_submit.wait() != 0:  # pragma: no cover
                    assert condor_submit.stderr
                    stderr_msg = ""
                    async for text in TextReceiveStream(condor_submit.stderr):
                        stderr_msg += text
                    raise CMHTCondorSubmitError(f"Bad htcondor submit: f{stderr_msg}")

        except Exception as e:
            raise CMHTCondorSubmitError(f"Bad htcondor submit: {e}") from e
