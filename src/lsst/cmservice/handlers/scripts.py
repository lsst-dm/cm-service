from __future__ import annotations

import os
from typing import Any

from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db.element import ElementMixin
from lsst.cmservice.db.script import Script

from ..common.bash import write_bash_script
from ..common.butler import (
    remove_collection_from_chain,
    remove_datasets_from_collections,
    remove_non_run_collections,
    remove_run_collections,
)
from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMBadExecutionMethodError, CMBadParameterTypeError, CMMissingScriptInputError
from ..db.step import Step
from .script_handler import ScriptHandler


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
        command = f"butler collection-chain {butler_repo} {output_coll}"
        if isinstance(input_colls, list):
            for input_coll in input_colls:
                command += f" {input_coll}"
        else:
            command += f" {input_colls}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_run_collections(butler_repo, output_coll)


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
        command = f"butler collection-chain {butler_repo} {output_coll} --mode prepend {input_coll}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_collection_from_chain(butler_repo, input_coll, output_coll)


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
        else:
            raise CMMissingScriptInputError(
                "Must specify what to collect in ChainCollectScriptHandler, jobs or steps",
            )
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler collection-chain {butler_repo} {output_coll}"
        for collect_coll_ in collect_colls:
            command += f" {collect_coll_}"
        for input_coll_ in input_colls:
            command += f" {input_coll_}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_non_run_collections(butler_repo, output_coll)


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
        command = f"butler associate {butler_repo} {output_coll}"
        command += f" --collections {input_coll}"
        if data_query:
            command += f' --where "{data_query}"'
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_non_run_collections(butler_repo, output_coll)


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
        command = f"butler associate {butler_repo} {output_coll}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_non_run_collections(butler_repo, output_coll)


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
        command = f"butler associate {butler_repo} {output_coll}"
        command += f" --collections {input_coll}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            input_coll = resolved_cols["input"]
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_datasets_from_collections(butler_repo, input_coll, output_coll)


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
        if not isinstance(parent, Step):
            raise CMBadExecutionMethodError(f"script {script} should only be run on steps, not {parent}")

        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            script_url = await self._set_script_files(session, script, data_dict["prod_area"])
            butler_repo = data_dict["butler_repo"]
            input_colls = resolved_cols["inputs"]
            output_coll = resolved_cols["output"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        prereq_colls: list[str] = []

        all_prereqs = await parent.get_all_prereqs(session)
        for prereq_step in all_prereqs:
            prereq_step_colls = await prereq_step.resolve_collections(session)
            prereq_colls.append(prereq_step_colls["step_public_output"])

        if not prereq_colls:
            prereq_colls.append(resolved_cols["global_inputs"])

        command = f"butler collection-chain {butler_repo} {output_coll}"
        if prereq_colls:
            for prereq_coll_ in prereq_colls:
                command += f" {prereq_coll_}"
        else:
            command += f" {input_colls}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_non_run_collections(butler_repo, output_coll)


class ResourceUsageScriptHandler(ScriptHandler):
    """Write the script to compute resource usage metrics for a campaign."""

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        # breakpoint()
        specification = await script.get_specification(session)
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        prod_area = os.path.expandvars(data_dict["prod_area"])
        script_url = await self._set_script_files(session, script, prod_area)
        butler_repo = data_dict["butler_repo"]
        lsst_distrib_dir = data_dict["lsst_distrib_dir"]
        lsst_version = data_dict["lsst_version"]
        usage_graph_url = os.path.expandvars(f"{prod_area}/{parent.fullname}.qgraph")

        resource_usage_script_template = await specification.get_script_template(
            session,
            data_dict["resource_usage_script_template"],
        )
        prepend = resource_usage_script_template.data["text"].replace(
            "{lsst_version}",
            lsst_version,
        )
        prepend = prepend.replace("{lsst_distrib_dir}", lsst_distrib_dir)
        if "custom_lsst_setup" in data_dict:
            custom_lsst_setup = data_dict["custom_lsst_setup"]
            prepend += f"\n{custom_lsst_setup}"

        command = f"build-gather-resource-usage-qg {butler_repo} {usage_graph_url} {resolved_cols['out']} "
        f"--output {resolved_cols['campaign_resource_usage']};pipetask run -b {butler_repo} -g "
        f"{usage_graph_url} -o {resolved_cols['campaign_resource_usage']} --register-dataset-types -j 16"

        await write_bash_script(script_url, command, prepend=prepend)

        return StatusEnum.prepared

    async def _purge_products(
        self, session: async_scoped_session, script: Script, to_status: StatusEnum
    ) -> None:
        """When the script is reset or the campaign is deleted, cleanup
        resource usage products."""
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        parent = await script.get_parent(session)
        if parent.level != LevelEnum.campaign:
            raise CMBadParameterTypeError(f"Script parent is a {parent.level}, not a LevelEnum.campaign")
        try:
            resource_coll = resolved_cols["campaign_resource_usage"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg
        if to_status.value < StatusEnum.running.value:
            remove_run_collections(butler_repo, resource_coll)
        return await super()._purge_products(session, script, to_status)


class ValidateScriptHandler(ScriptHandler):
    """Write a script to run validate after processing

    This will create:
    `parent.collections['validation']`

    FIXME (How? chained or tagged)
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
        command = f"pipetask FIXME {butler_repo} {input_coll} {output_coll}"
        await write_bash_script(script_url, command, prepend="#!/usr/bin/bash\n", **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        resolved_cols = await script.resolve_collections(session)
        data_dict = await script.data_dict(session)
        try:
            output_coll = resolved_cols["output"]
            butler_repo = data_dict["butler_repo"]
        except KeyError as msg:
            raise CMMissingScriptInputError(f"{script.fullname} missing an input: {msg}") from msg

        if to_status.value <= StatusEnum.running.value:
            remove_run_collections(butler_repo, output_coll)
