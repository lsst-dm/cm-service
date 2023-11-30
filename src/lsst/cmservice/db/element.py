from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import NodeTypeEnum, StatusEnum
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

    col_names_for_table = ["id", "fullname", "spec_block_id", "handler", "status", "superseded"]

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
        async with session.begin_nested():
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
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["jobs_"])
            for job_ in self.jobs_:
                if remaining_only and job_.status.value >= StatusEnum.accepted.value:
                    continue
                if skip_superseded and job_.superseded:
                    continue
                ret_list.append(job_)
        return ret_list

    async def retry_script(
        self,
        session: async_scoped_session,
        script_name: str,
    ) -> Script:
        """Retry a script

        This will make a new `Script` in the DB and
        mark the previous one as superseded

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
            raise ValueError(
                f"Expected one active script matching {script_name} for {self.fullname}, got {len(scripts)}",
            )
        the_script = scripts[0]
        if the_script.status.value > StatusEnum.rejected.value:
            raise ValueError(
                f"Can only retry failed/rejected scripts, {the_script.fullname} is {the_script.status.value}",
            )
        new_script = await the_script.copy_script(session)
        await the_script.update_values(session, superseded=True)
        await session.commit()
        return new_script

    async def rescue_job(
        self,
        session: async_scoped_session,
    ) -> Job:
        """Create a rescue `Job`

        This will make a new `Job` in the DB

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        job: Job
            Newly created Job
        """
        jobs = await self.get_jobs(session)
        rescuable_jobs = []
        for job_ in jobs:
            if job_.status == StatusEnum.rescuable:
                rescuable_jobs.append(job_)
            else:
                raise ValueError(f"Found unrescuable job: {job_.fullname}")
        if not rescuable_jobs:
            raise ValueError(f"Expected at least one rescuable job for {self.fullname}, got 0")
        latest_resuable_job = rescuable_jobs[-1]
        new_job = await latest_resuable_job.copy_job(session, self)
        await session.commit()
        return new_job

    async def mark_job_rescued(
        self,
        session: async_scoped_session,
    ) -> list[Job]:
        """Mark jobs as `rescued` once one of their siblings is `accepted`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        jobs: List[Job]
            Jobs marked as `rescued`
        """
        jobs = await self.get_jobs(session)
        has_accepted = False
        ret_list = []
        for job_ in jobs:
            if job_.status == StatusEnum.rescuable:
                await job_.update_values(session, status=StatusEnum.rescued)
                ret_list.append(job_)
            elif job_.status != StatusEnum.accepted:
                raise ValueError(f"Job should be rescuable or accepted: {job_.fullname} is {job_.status}")
            else:
                if has_accepted:
                    raise ValueError(f"More that one accepted job found: {job_.fullname}")
                has_accepted = True
        if not has_accepted:
            raise ValueError(f"Expected at least one accepted job for {self.fullname}, got 0")
        await session.commit()
        return ret_list
