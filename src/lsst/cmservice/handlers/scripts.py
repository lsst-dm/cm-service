from __future__ import annotations

import os
import textwrap
from typing import Any

from anyio import Path
from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.bash import write_bash_script
from ..common.butler import (
    remove_collection_from_chain,
    remove_datasets_from_collections,
    remove_non_run_collections,
    remove_run_collections,
)
from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMBadExecutionMethodError, CMMissingScriptInputError, test_type_and_raise
from ..common.logging import LOGGER
from ..config import config
from ..db.element import ElementMixin
from ..db.script import Script
from ..db.step import Step
from .script_handler import ScriptHandler

logger = LOGGER.bind(module=__name__)


class NullScriptHandler(ScriptHandler):
    """A no-op script, mostly for testing"""

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as e:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {e}") from e

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        command = f"echo trivial {butler_repo} {output_coll}"

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        _resolved_cols = await script.resolve_collections(session)
        _data_dict = await script.data_dict(session)


class ChainCreateScriptHandler(ScriptHandler):
    """Write a script to chain together collections

    This will take

    `script.collections['inputs']`

    and chain them into

    `script.collections['output']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            input_colls = resolved_cols["inputs"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = f"{config.butler.butler_bin} collection-chain {butler_repo} {output_coll}"
        # This is here out of paranoia.
        # script.resolved_collections should convert the list to a string
        if isinstance(input_colls, list):  # pragma: no cover
            for input_coll in input_colls:
                command += f" {input_coll}"
        else:
            command += f" {input_colls}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_run_collections(butler_repo, output_coll, fake_reset=fake_reset)


class ChainPrependScriptHandler(ScriptHandler):
    """Write a script to prepend a collection to a chain

    This will take

    `script.collections['input']`

    and chain --prepend it into

    `script.collections['output']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            input_coll = resolved_cols["input"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = (
            f"{config.butler.butler_bin} collection-chain "
            f"{butler_repo} {output_coll} --mode prepend {input_coll}"
        )

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_collection_from_chain(butler_repo, input_coll, output_coll, fake_reset=fake_reset)


class ChainCollectScriptHandler(ScriptHandler):
    """Write a script to collect stuff from an `Element` after processing

    This will create:
    `script.collections['output']`

    and collect all of the output collections at a given level to it
    and then append

    `script.collections['inputs']` to it
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            input_colls = resolved_cols["inputs"]
            to_collect = data_dict["collect"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        collect_colls = []
        if to_collect == "jobs":
            jobs = await parent.get_jobs(session)
            for job_ in jobs:
                job_colls = await job_.resolve_collections(session)
                collect_colls.append(job_colls["job_run"])
        elif to_collect == "steps":
            for step_ in await parent.children(session):
                step_colls = await step_.resolve_collections(session)
                collect_colls.append(step_colls["step_output"])
                collect_colls = collect_colls[::-1]
        else:  # pragma: no cover
            raise CMMissingScriptInputError(
                "Must specify what to collect in ChainCollectScriptHandler, jobs or steps",
            )
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"{config.butler.butler_bin} collection-chain {butler_repo} {output_coll}"
        for collect_coll_ in collect_colls:
            command += f" {collect_coll_}"
        for input_coll_ in input_colls:
            command += f" {input_coll_}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_non_run_collections(butler_repo, output_coll, fake_reset=fake_reset)


class TagInputsScriptHandler(ScriptHandler):
    """Write a script to make a TAGGED collection of inputs

    This will take

    `script.collections['input']`

    and make a TAGGED collection at

    `script.collections['output']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            input_coll = resolved_cols["input"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
            data_query = data_dict.get("data_query")
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = f"{config.butler.butler_bin} associate {butler_repo} {output_coll}"
        command += f" --collections {input_coll}"
        command += f' --where "{data_query}"' if data_query else ""

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_non_run_collections(butler_repo, output_coll, fake_reset=fake_reset)


class TagCreateScriptHandler(ScriptHandler):
    """Make an empty TAGGED collection

    This will make a TAGGED collection at

    `script.collections['output']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = f"{config.butler.butler_bin} associate {butler_repo} {output_coll}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_non_run_collections(butler_repo, output_coll, fake_reset=fake_reset)


class TagAssociateScriptHandler(ScriptHandler):
    """Add datasets to a TAGGED collection

    This will add datasets from

    `script.collections['input']`
    to
    `script.collections['output']`
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = f"{config.butler.butler_bin} associate {butler_repo} {output_coll}"
        command += f" --collections {input_coll}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_datasets_from_collections(butler_repo, input_coll, output_coll, fake_reset=fake_reset)


class PrepareStepScriptHandler(ScriptHandler):
    """Make the input collection for a step

    This will create a chained collection

    `script.collections['output']`

    by taking the output collections of all the
    prerequisite steps, or

    `script.collections['campaign_input'] if the
    step has no inputs

    it will then append
    `script.collections['output']` to the output collection
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        test_type_and_raise(parent, Step, "PrepareStepScriptHandler._write_script parent")

        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
            output_coll = resolved_cols["output"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        prereq_colls: list[str] = []

        all_prereqs = await parent.get_all_prereqs(session)  # type: ignore
        for prereq_step in all_prereqs:
            prereq_step_colls = await prereq_step.resolve_collections(session)
            prereq_colls.append(prereq_step_colls["step_public_output"])

        if not prereq_colls:
            prereq_colls.append(resolved_cols["global_inputs"])

        command = f"{config.butler.butler_bin} collection-chain {butler_repo} {output_coll}"
        for prereq_coll_ in prereq_colls:
            command += f" {prereq_coll_}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_non_run_collections(butler_repo, output_coll, fake_reset=fake_reset)


class ResourceUsageScriptHandler(ScriptHandler):
    """Write the script to compute resource usage metrics for a campaign."""

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        usage_graph_url = os.path.expandvars(f"{prod_area}/{parent.fullname}/resource_usage.qgraph")

        command = (
            f"{config.bps.resource_usage_bin} {butler_repo} {usage_graph_url} "
            f"{resolved_cols['campaign_output']} --output {resolved_cols['campaign_resource_usage']};"
            f"{config.bps.pipetask_bin} run -b {butler_repo} -g {usage_graph_url} "
            f"-o {resolved_cols['campaign_resource_usage']} --register-dataset-types -j {config.bps.n_jobs}"
        )

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)

        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        """When the script is reset or the campaign is deleted, cleanup
        resource usage products."""
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        parent = await script.get_parent(session)
        if parent.level != LevelEnum.campaign:  # pragma: no cover
            raise CMBadExecutionMethodError(f"Script parent is a {parent.level}, not a LevelEnum.campaign")
        try:
            resource_coll = resolved_cols["campaign_resource_usage"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        await remove_run_collections(butler_repo, resource_coll, fake_reset=fake_reset)
        return await super()._purge_products(session, script, to_status, fake_reset=fake_reset)


class HipsMapsScriptHandler(ScriptHandler):
    """Write the script to make the HiPS maps for a campaign."""

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        hips_maps_graph_url = os.path.expandvars(f"{prod_area}/{parent.fullname}/hips_maps.qgraph")

        hips_pipeline_yaml = await Path(
            os.path.expandvars("${CM_CONFIGS}") + data_dict["hips_pipeline_yaml_path"]
        ).resolve()
        gen_hips_both_yaml = await Path(
            os.path.expandvars("${CM_CONFIGS}") + data_dict["hips_pipeline_config_path"]
        ).resolve()

        # Note: The pipetask command below features a `-j N` which requests
        # N nodes to run. This will guarantee that the HIPS maps generate at
        # a reasonable rate. However, when allocating nodes for HTCondor,
        # the user should allocate at least 16 so that this can execute
        # properly. Future effort should be devoted to getting a number like
        # this out of a campaign data dict and managing it in cm-service.

        command = f"""# First we get the output of the generated pixels and then format it so the output of
        # the first command can be used as input to the next.
        output=$({config.hips.high_res_bin} segment -b {butler_repo} \
        -p {hips_pipeline_yaml} -i {resolved_cols["campaign_output"]} -o 1);
        # Then, we take pixels from previous commands and use to build the hips maps graph.
        pixels=$(echo '$output' | grep -Eo '[0-9]+' | tr '\\n' ' ');
        {config.hips.high_res_bin} build -b {butler_repo} -p {hips_pipeline_yaml} \
        -i {resolved_cols["campaign_output"]} --output {resolved_cols["campaign_hips_maps"]} \
        --pixels $pixels -q {hips_maps_graph_url};
        # Now we pipetask run the graph
        {config.bps.pipetask_bin} --long-log --log-level=INFO run -j {config.bps.n_jobs} -b {butler_repo} \
        --output {resolved_cols["campaign_hips_maps"]} --register-dataset-types -g {hips_maps_graph_url};
        # Generate HIPS 9-level .png images
        {config.bps.pipetask_bin} --long-log --log-level=INFO run -j {config.bps.n_jobs} -b {butler_repo} \
        -i {resolved_cols["campaign_output"]} --output {resolved_cols["campaign_hips_maps"]} \
        -p {gen_hips_both_yaml} -c 'generateHips:hips_base_uri=\
        {config.hips.uri}/{resolved_cols["campaign_hips_maps"]}' \
        -c 'generateColorHips:hips_base_uri={config.hips.uri}/{resolved_cols["campaign_hips_maps"]}' \
        --register-dataset-types
        """

        # Remove indentation from multiline string
        command = textwrap.dedent(command)
        # Remove additional whitespace
        command = command.replace(8 * " ", "")
        # Strip leading/trailing spaces just in case
        command = "\n".join([line.strip() for line in command.splitlines()])

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)

        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        """When the script is reset or the campaign is deleted, cleanup
        hips maps products."""
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        parent = await script.get_parent(session)
        if parent.level != LevelEnum.campaign:  # pragma: no cover
            raise CMBadExecutionMethodError(f"Script parent is a {parent.level}, not a LevelEnum.campaign")
        try:
            hips_maps_coll = resolved_cols["campaign_hips_maps"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:  # pragma: no cover
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        if to_status.value < StatusEnum.running.value:
            await remove_run_collections(butler_repo, hips_maps_coll, fake_reset=fake_reset)
        return await super()._purge_products(session, script, to_status)


class ValidateScriptHandler(ScriptHandler):
    """Write a script to run validate after processing

    This will create:
    `parent.collections['validation']`

    FIXME: what script do we actually run here?
    """

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        command = f"{config.bps.pipetask_bin} validate {butler_repo} {input_coll} {output_coll}"

        template_values = {
            "script_method": script.run_method.name,
            **data_dict,
        }

        await write_bash_script(script_url, command, values=template_values)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        await remove_run_collections(butler_repo, output_coll, fake_reset=fake_reset)
