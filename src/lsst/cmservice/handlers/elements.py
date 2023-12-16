from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import numpy as np
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db.campaign import Campaign
from lsst.cmservice.db.element import ElementMixin
from lsst.cmservice.db.group import Group
from lsst.cmservice.db.job import Job
from lsst.cmservice.db.script import Script
from lsst.daf.butler import Butler

from ..common.enums import StatusEnum
from ..common.errors import BadExecutionMethodError, MissingScriptInputError
from ..common.slurm import check_slurm_job
from .functions import add_steps
from .script_handler import FunctionHandler


def parse_bps_stdout(url: str) -> dict[str, str]:
    """Parse the std from a bps submit job"""
    out_dict = {}
    with open(url, encoding="utf8") as fin:
        line = fin.readline()
        while line:
            tokens = line.split(":")
            if len(tokens) != 2:  # pragma: no cover
                line = fin.readline()
                continue
            out_dict[tokens[0]] = tokens[1]
            line = fin.readline()
    return out_dict


class RunElementScriptHandler(FunctionHandler):
    """Shared base class to handling running and
    checking of Scripts that mangage the children
    of elements

    E.g.,  RunGroupsScriptHandler and RunStepsScriptHandler
    """

    async def _do_run(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        min_val = StatusEnum.accepted.value
        for child_ in await parent.children(session):
            _child_changed, child_status = await child_.process(session, **kwargs)
            min_val = min(min_val, child_status.value)

        status = StatusEnum.accepted if min_val >= StatusEnum.accepted.value else StatusEnum.running

        await script.update_values(session, status=status)
        return status

    async def _do_check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        min_val = StatusEnum.accepted.value
        for child_ in await parent.children(session):
            _child_changed, child_status = await child_.process(session, **kwargs)
            min_val = min(min_val, child_status.value)

        status = StatusEnum.accepted if min_val >= StatusEnum.accepted.value else StatusEnum.running

        await script.update_values(session, status=status)
        return status


class RunJobsScriptHandler(RunElementScriptHandler):
    """Create a `Job` in the DB

    FIXME
    """

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        child_config = await parent.get_child_config(session)
        spec_aliases = await parent.get_spec_aliases(session)
        specification = await parent.get_specification(session)
        spec_block_name = child_config.pop("spec_block", None)
        if spec_block_name is None:
            raise MissingScriptInputError(f"child_config for {script.fullname} does not contain spec_block")
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block_assoc_name = f"{specification.name}#{spec_block_name}"
        _new_job = await Job.create_row(
            session,
            name="job",
            attempt=0,
            parent_name=parent.fullname,
            spec_block_assoc_name=spec_block_assoc_name,
            **child_config,
        )
        await script.update_values(session, status=StatusEnum.prepared)
        return StatusEnum.running

    async def _check_slurm_job(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        slurm_id: str,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        slurm_status = await check_slurm_job(slurm_id)
        if slurm_status is None:
            slurm_status = StatusEnum.running
        if slurm_status == StatusEnum.accepted:
            await script.update_values(session, status=StatusEnum.reviewable)
            bps_dict = parse_bps_stdout(script.log_url)
            panda_url = bps_dict["Run Id"]
            async with session.begin_nested():
                await parent.update_values(session, wms_stamp_url=panda_url)
            return StatusEnum.reviewable
        return slurm_status

    async def review(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        jobs = await parent.get_jobs(session, remaining_only=not kwargs.get("force_check", False))
        for job_ in jobs:
            job_status = await job_.run_check(session)
            if job_status < StatusEnum.accepted:
                status = StatusEnum.reviewable  # FIXME
                await script.update_values(session, status=status)
                return status
        status = StatusEnum.accepted
        await script.update_values(session, status=status)
        return status


class Splitter:
    @classmethod
    async def split(  # pylint: disable=unused-argument
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:
        yield


class NoSplit(Splitter):
    @classmethod
    async def split(
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:
        ret_dict: dict = {"data": {}}
        base_query = kwargs["base_query"]
        ret_dict["data"]["data_query"] = f"{base_query}"
        yield ret_dict


class SplitByVals(Splitter):
    @classmethod
    async def split(
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:
        ret_dict: dict = {"data": {}}
        split_vals = kwargs.get("split_vals", [])
        base_query = kwargs["base_query"]
        split_field = kwargs["split_field"]
        for split_val_ in split_vals:
            ret_dict["data"]["data_query"] = f"{base_query} AND {split_field} IN ({split_val_})"
            yield ret_dict


class SplitByQuery(Splitter):
    @classmethod
    async def split(
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:
        data = await parent.data_dict(session)
        collections = await parent.resolve_collections(session)
        butler_repo = data["butler_repo"]
        input_coll = collections["step_input"]
        campaign_input_coll = collections["campaign_input"]
        campaign_ancil_coll = collections["campaign_ancillary"]
        base_query = kwargs["base_query"]
        split_field = kwargs["split_field"]
        split_dataset = kwargs["split_dataset"]
        split_min_groups = kwargs.get("split_min_groups", 1)
        split_max_group_size = kwargs.get("split_max_group_size", 100000000)
        fake_status = kwargs.get("fake_status", None)
        if not fake_status:
            butler = Butler.from_config(
                butler_repo,
                collections=[input_coll, campaign_input_coll, campaign_ancil_coll],
            )
            itr = butler.registry.queryDataIds([split_field], datasets=split_dataset).subset(unique=True)
            sorted_field_values = np.sort(np.array([x_[split_field] for x_ in itr]))
        else:
            sorted_field_values = np.arange(10)
        n_matched = sorted_field_values.size

        step_size = min(split_max_group_size, int(n_matched / split_min_groups))

        data_queries = []
        previous_idx = 0
        idx = 0

        while idx < n_matched:
            idx += step_size
            min_val = sorted_field_values[previous_idx]
            if idx >= n_matched:
                data_queries.append(f"({min_val} <= {split_field})")
            else:
                max_val = max(sorted_field_values[idx], min_val + 1)
                data_queries.append(f"({min_val} <= {split_field}) and ({split_field} < {max_val})")
            previous_idx = idx

        ret_dict: dict = {"data": {}}
        for dq_ in data_queries:
            data_query = base_query
            if dq_ is not None:
                data_query += f" AND {dq_}"
            ret_dict["data"]["data_query"] = data_query
            yield ret_dict


SPLIT_CLASSES = {
    "no_split": NoSplit,
    "split_by_query": SplitByQuery,
    "split_by_vals": SplitByVals,
}


class RunGroupsScriptHandler(RunElementScriptHandler):
    """Build and manages the groups associated to a `Step`"""

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        child_config = await parent.get_child_config(session)
        spec_aliases = await parent.get_spec_aliases(session)
        specification = await parent.get_specification(session)
        spec_block_name = child_config.pop("spec_block", None)
        if spec_block_name is None:
            raise MissingScriptInputError(f"child_config for {script.fullname} does not contain spec_block")
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        spec_block_assoc_name = f"{specification.name}#{spec_block_name}"
        fake_status = kwargs.get("fake_status")

        split_method = child_config.pop("split_method", "no_split")
        splitter = SPLIT_CLASSES[split_method]

        i = 0
        group_gen = splitter.split(session, script, parent, fake_status=fake_status, **child_config)

        async for group_dict_ in group_gen:
            _new_group = await Group.create_row(
                session,
                name=f"group{i}",
                spec_block_assoc_name=spec_block_assoc_name,
                parent_name=parent.fullname,
                **group_dict_,
            )
            i += 1

        status = StatusEnum.prepared
        await script.update_values(session, status=status)
        return status


class RunStepsScriptHandler(RunElementScriptHandler):
    """Build and manages the Steps associated to a `Campaign`

    This will use the

    `campaign.child_config` -> to set the steps
    """

    async def _do_prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        if not isinstance(parent, Campaign):
            raise BadExecutionMethodError(f"Can not run script {script} on {parent}")
        spec_block = await parent.get_spec_block(session)
        child_configs = spec_block.steps
        await add_steps(session, parent, child_configs)
        status = StatusEnum.prepared
        await script.update_values(session, status=status)
        return status
