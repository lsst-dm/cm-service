from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import LevelEnum, NodeTypeEnum, StatusEnum
from ..common.errors import CMBadStateTransitionError, CMTooManyActiveScriptsError
from ..models.merged_product_set import MergedProductSetDict
from ..models.merged_task_set import MergedTaskSetDict
from ..models.merged_wms_task_report import MergedWmsTaskReportDict
from .node import NodeMixin

if TYPE_CHECKING:
    from .job import Job
    from .script import Script


class ElementMixin(NodeMixin):
    """Mixin class to define common features of database rows
    descriping data processing elements, i.e.,
    `Campaign`, `Step`, `Group`, `Job`
    """

    scripts_: Any
    jobs_: Any
    level: Any

    col_names_for_table = ["id", "fullname", "status", "superseded"]

    @property
    def node_type(self) -> NodeTypeEnum:
        """There are `Element` nodes"""
        return NodeTypeEnum.element

    async def get_scripts(
        self,
        session: async_scoped_session,
        script_name: str | None = None,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[Script]:
        """Return the `Script`s associated to an element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script_name: str | None
            If provided, only return scripts with this name

        remaining_only: bool
            If True only include Scripts that are not revieable or accepted

        skip_superseded: bool
            If True don't inlcude Scripts that are marked superseded

        Returns
        -------
        scripts : List[Script]
            The requested scripts
        """
        ret_list = []
        await session.refresh(self, attribute_names=["scripts_"])
        for script_ in self.scripts_:
            if script_name and script_name != script_.name:
                continue
            if remaining_only and script_.status.value >= StatusEnum.reviewable.value:
                continue
            if skip_superseded and script_.superseded:
                continue
            ret_list.append(script_)
        return ret_list

    async def get_jobs(
        self,
        session: async_scoped_session,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[Job]:
        """Return the `Job`s associated to an element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        remaining_only: bool
            If True only include Jobs that are not already accepted

        skip_superseded: bool
            If True don't inlcude Jobs that are marked superseded

        Returns
        -------
        jobs : List[Jobs]
            The requested Jobs
        """
        ret_list = []
        await session.refresh(self, attribute_names=["jobs_"])
        for job_ in self.jobs_:
            if remaining_only and job_.status.value >= StatusEnum.accepted.value:
                continue
            if skip_superseded and job_.superseded:
                continue
            ret_list.append(job_)
        return ret_list

    async def get_all_scripts(
        self,
        session: async_scoped_session,
        *,
        remaining_only: bool = False,
        skip_superseded: bool = True,
    ) -> list[Script]:
        """Return all the scripts associated to an ELement

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        remaining_only: bool
            If True only include Jobs that are not already accepted

        skip_superseded: bool
            If True don't inlcude Jobs that are marked superseded

        Returns
        -------
        scripts : List[Script]
            The requested Scripts
        """
        ret_list = await self.get_scripts(
            session,
            script_name=None,
            remaining_only=remaining_only,
            skip_superseded=skip_superseded,
        )
        children = await self.children(session)
        for child_ in children:
            ret_list += await child_.get_all_scripts(
                session,
                remaining_only=remaining_only,
                skip_superseded=skip_superseded,
            )
        return ret_list

    async def children(
        self,
        session: async_scoped_session,
    ) -> Iterable:
        """Maps to [] for consistency"""
        assert session  # for mypy
        return []

    async def retry_script(
        self,
        session: async_scoped_session,
        script_name: str,
    ) -> Script:
        """Retry a script

        This will retry a script

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script_name: str
            The name of the script

        Returns
        -------
        script : Script
        """
        scripts = await self.get_scripts(session, script_name)
        if len(scripts) != 1:
            raise CMTooManyActiveScriptsError(
                f"Expected one active script matching {script_name} for {self.fullname}, got {len(scripts)}",
            )
        the_script = scripts[0]
        if the_script.status.value > StatusEnum.rejected.value:
            raise CMBadStateTransitionError(
                f"Can only retry failed/rejected scripts, {the_script.fullname} is {the_script.status.value}",
            )
        _new_status = await the_script.reset_script(session, StatusEnum.waiting)
        return the_script

    async def estimate_sleep_time(
        self,
        session: async_scoped_session,
        job_sleep: int = 150,
        script_sleep: int = 15,
    ) -> int:
        """Estimate how long to sleep before calling process again

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        job_sleep: int = 150
            Time to sleep if jobs are running

        script_sleep: int = 15
            Time to sleep if scripts are running

        Returns
        -------
        sleep_time : int
            Time to sleep in seconds
        """
        sleep_time = 10
        if self.level == LevelEnum.job:
            all_jobs = []
        else:
            all_jobs = await self.get_jobs(session)
        for job_ in all_jobs:
            if job_.status == StatusEnum.running:
                sleep_time = min(job_sleep, sleep_time)
        all_scripts = await self.get_all_scripts(session)
        for script_ in all_scripts:
            if script_.status == StatusEnum.running:
                sleep_time = min(script_sleep, sleep_time)
        return sleep_time

    async def get_wms_reports(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedWmsTaskReportDict:
        """Get the WmwTaskReports associated to this element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        the_dict: MergedWmsTaskReportDict
             Requested reports
        """
        raise NotImplementedError()

    async def get_tasks(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedTaskSetDict:
        """Get the TaskSet associated to this element

        script_sleep: int = 15
            Time to sleep if scripts are running

        Returns
        -------
        the_dict : MergedTaskSetDict
             Requested reports
        """
        raise NotImplementedError()

    async def get_products(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> MergedProductSetDict:
        """Get the ProductSet associated to this element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        the_dict : MergedProductSetDict
             Requested reports
        """
        raise NotImplementedError()

    async def review(
        self,
        session: async_scoped_session,
        **kwargs: Any,
    ) -> StatusEnum:
        """Run review() function on this Element

        This will create a `Handler` and
        pass this node to it for review

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        handler = await self.get_handler(session)
        return await handler.review(session, self, **kwargs)
