from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import partial
from typing import Any

import numpy as np
from anyio import to_thread
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.daf.butler import Butler

from ..common.enums import StatusEnum
from ..common.errors import CMMissingScriptInputError, test_type_and_raise
from ..config import config
from ..db.campaign import Campaign
from ..db.element import ElementMixin
from ..db.group import Group
from ..db.job import Job
from ..db.script import Script
from .script_handler import FunctionHandler


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

    This will create a single job per group,
    which ideally would process the workflow for
    that group.

    If needed rescue jobs can be attached to the
    group.

    The review_script method is there to check on the
    status of the jobs.
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
        spec_block_name = child_config.pop("spec_block", None)
        if spec_block_name is None:  # pragma: no cover
            raise CMMissingScriptInputError(f"child_config for {script.fullname} does not contain spec_block")
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)
        _new_job = await Job.create_row(
            session,
            name="job",
            attempt=0,
            parent_name=parent.fullname,
            spec_block_name=spec_block_name,
            **child_config,
        )
        await script.update_values(session, status=StatusEnum.prepared)
        return StatusEnum.running

    async def review_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        jobs = await parent.get_jobs(session, remaining_only=not kwargs.get("force_check", False))
        fake_status = kwargs.get("fake_status", config.mock_status)
        for job_ in jobs:
            job_status = job_.status if fake_status is None else fake_status
            if job_status.value < StatusEnum.accepted.value:
                status = StatusEnum.reviewable
                await script.update_values(session, status=status)
                return status
        status = StatusEnum.accepted
        await script.update_values(session, status=status)
        return status


class Splitter:
    """Class to split Steps into Groups"""

    @classmethod
    async def split(
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:  # pragma: no cover
        """Create a generator that will split a step into groups

        Parameters
        ----------
        session: async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        generator : AsyncGenerator
        """
        yield


class NoSplit(Splitter):
    """Create a single Group for a Step"""

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
    """Create groups from a Step by using a provided set of lists to make DB
    queries.
    """

    @classmethod
    async def split(
        cls,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> AsyncGenerator:  # pragma: no cover
        ret_dict: dict = {"data": {}}
        split_vals = kwargs.get("split_vals", [])
        base_query = kwargs["base_query"]
        split_field = kwargs["split_field"]
        for split_val_ in split_vals:
            ret_dict["data"]["data_query"] = f"{base_query} AND {split_field} IN ({split_val_})"
            yield ret_dict


class SplitByQuery(Splitter):
    """Create groups from a Step by making a DB query to get the total number
    of values of a particular field, then construct queries to split those
    values into a number of groups.
    """

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
        base_query = kwargs["base_query"]
        split_field = kwargs["split_field"]
        split_dataset = kwargs["split_dataset"]
        split_min_groups = kwargs.get("split_min_groups", 1)
        split_max_group_size = kwargs.get("split_max_group_size", 100000000)
        mock_butler: bool = kwargs.get("fake_status", config.butler.mock)
        if mock_butler:
            sorted_field_values = np.arange(10)
        else:
            butler_f = partial(
                Butler.from_config,
                butler_repo,
                collections=[input_coll, campaign_input_coll],
                without_datastore=True,
            )
            butler = await to_thread.run_sync(butler_f)
            itr_q_f = partial(
                butler.registry.queryDataIds,
                [split_field],
                datasets=split_dataset,
            )
            itr_q = await to_thread.run_sync(itr_q_f)
            itr_f = partial(
                itr_q.subset,
                unique=True,
            )
            itr = await to_thread.run_sync(itr_f)
            sorted_field_values = np.sort(np.array([x_[split_field] for x_ in itr]))
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
            data_query += f" AND {dq_}"
            ret_dict["data"]["data_query"] = data_query
            yield ret_dict


SPLIT_CLASSES: dict[str, type[Splitter]] = {
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
        spec_block_name = child_config.pop("spec_block", None)
        if spec_block_name is None:  # pragma: no cover
            raise CMMissingScriptInputError(f"child_config for {script.fullname} does not contain spec_block")
        spec_block_name = spec_aliases.get(spec_block_name, spec_block_name)

        split_method: str = child_config.pop("split_method", "no_split")
        splitter: type[Splitter] = SPLIT_CLASSES[split_method]

        i = 0
        async for group_dict_ in splitter.split(session, script, parent, **child_config):
            _ = await Group.create_row(
                session,
                name=f"group{i}",
                spec_block_name=spec_block_name,
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
        test_type_and_raise(parent, Campaign, "RunStepsScriptHandler parent")
        status = StatusEnum.prepared
        await script.update_values(session, status=status)
        return status
