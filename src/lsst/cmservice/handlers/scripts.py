from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db.element import ElementMixin
from lsst.cmservice.db.script import Script

from ..common.bash import write_bash_script
from ..common.enums import StatusEnum
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
        output_coll = resolved_cols["output"]
        input_colls = resolved_cols["inputs"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler collection-chain {butler_repo} {output_coll}"
        for input_coll in input_colls:
            command += f" {input_coll}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        output_coll = resolved_cols["output"]
        input_coll = resolved_cols["input"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler collection-chain {butler_repo} {output_coll} --mode prepend {input_coll}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        output_coll = resolved_cols["output"]
        input_colls = resolved_cols["inputs"]
        data_dict = await script.data_dict(session)
        to_collect = data_dict["collect"]
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
            raise ValueError("Must specify what to collect in ChainCollectScriptHandler, jobs or steps")
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler collection-chain {butler_repo} {output_coll}"
        for collect_coll_ in collect_colls:
            command += f" {collect_coll_}"
        for input_coll_ in input_colls:
            command += f" {input_coll_}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        output_coll = resolved_cols["output"]
        input_coll = resolved_cols["input"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        data_query = data_dict.get("data_query")
        command = f"butler associate {butler_repo} {output_coll}"
        command += f" --collection {input_coll}"
        if data_query:
            command += f' --where "{data_query}"'
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        output_coll = resolved_cols["output"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler associate {butler_repo} {output_coll}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        input_coll = resolved_cols["input"]
        output_coll = resolved_cols["output"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler associate {butler_repo} {output_coll}"
        command += f" --collections {input_coll}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
            raise TypeError(f"script {script} should only be run on steps, not {parent}")
        resolved_cols = await script.resolve_collections(session)
        input_colls = resolved_cols["inputs"]
        output_coll = resolved_cols["output"]
        prereq_colls: list[str] = []

        async with session.begin_nested():
            await session.refresh(parent, attribute_names=["prereqs_"])
            for prereq_ in parent.prereqs_:
                await session.refresh(prereq_, attribute_names=["prereq_"])
                prereq_step = prereq_.prereq_
                prereq_step_colls = await prereq_step.resolve_collections(session)
                prereq_colls.append(prereq_step_colls["step_output"])
        if not prereq_colls:
            prereq_colls += resolved_cols["global_inputs"]

        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"butler collection-chain {butler_repo} {output_coll} --collections"
        if prereq_colls:
            for prereq_coll_ in prereq_colls:
                command += f" {prereq_coll_}"
        else:
            for input_coll_ in input_colls:
                command += f" {input_coll_}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared


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
        input_coll = resolved_cols["input"]
        output_coll = resolved_cols["output"]
        data_dict = await script.data_dict(session)
        script_url = await self._set_script_files(session, script, data_dict["prod_area"])
        butler_repo = data_dict["butler_repo"]
        command = f"pipetask FIXME {butler_repo} {input_coll} {output_coll}"
        await write_bash_script(script_url, command, **data_dict)
        await script.update_values(session, script_url=script_url, status=StatusEnum.prepared)
        return StatusEnum.prepared
