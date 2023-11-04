from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import StatusEnum
from ..db.element import ElementMixin
from ..db.handler import Handler
from ..db.node import NodeMixin
from ..db.script import Script
from ..db.script_dependency import ScriptDependency


class ElementHandler(Handler):
    """SubClass of Handler to deal with generic 'Element' operations,
    i.e., stuff shared between Campaign, Step, Group
    """

    @staticmethod
    async def _add_prerequisite(
        session: async_scoped_session,
        script_id: int,
        prereq_id: int,
    ) -> ScriptDependency:
        """Add a prerequite to running a `Script`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script_id: int
            Id for the script that depends on the other

        prereq_id: int,
            Id for the script that is a prerequisite for the other

        Returns
        -------
        new_depend : ScriptDependency
            Newly created dependency
        """
        new_depend = await ScriptDependency.create_row(
            session,
            prereq_id=prereq_id,
            depend_id=script_id,
        )
        async with session.begin_nested():
            await session.refresh(new_depend)
            return new_depend

    async def process(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Process a `Element` as much as possible

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        node: NodeMixin
            `Node` in question

        kwargs: Any
            Used to override processing configuration

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = node.status
        # Need this so mypy doesn't think we are passing in Script
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)
        if status == StatusEnum.waiting:
            is_ready = await node.check_prerequisites(session)
            if is_ready:
                status = StatusEnum.ready
        if status == StatusEnum.ready:
            status = await self.prepare(session, node)
        if status == StatusEnum.prepared:
            status = await self.continue_processing(session, node, **kwargs)
        if status == StatusEnum.running:
            status = await self.check(session, node, **kwargs)
            if status == StatusEnum.running:
                status = await self.continue_processing(session, node, **kwargs)
        if status == StatusEnum.reviewable:
            status = await self.review(session, node, *kwargs)
        if status != node.status:
            await node.update_values(session, status=status)
        return status

    async def run_check(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        status = node.status
        # Need this so mypy doesn't think we are passing in Script
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)
        status = await self.check(session, node, **kwargs)
        return status

    async def prepare(
        self,
        session: async_scoped_session,
        element: ElementMixin,
    ) -> StatusEnum:
        """Prepare `Element` for processing

        This means creating database entries for scripts and
        dependencies between them

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        async with session.begin_nested():
            await session.refresh(element, attribute_names=["spec_block_"])
            spec_block = element.spec_block_
            await session.refresh(spec_block, attribute_names=["spec_"])
            spec = spec_block.spec_
            spec_name = spec.name

        spec_aliases = await element.get_spec_aliases(session)

        script_ids_dict = {}
        prereq_pairs = []
        for script_item in spec_block.scripts:
            try:
                script_vals = script_item["Script"].copy()
            except KeyError as msg:
                raise KeyError(f"Expected Script tag, found {script_item.keys()}") from msg
            if not isinstance(script_vals, dict):
                raise TypeError(f"Script Tag should be a dict not {script_vals}")
            try:
                script_name = script_vals.pop("name")
            except KeyError as msg:
                raise KeyError(f"Unnnamed Script block {script_vals}") from msg
            script_spec_block = script_vals.get("spec_block", None)
            if script_spec_block is None:
                raise AttributeError(f"Script block {script_name} does not contain spec_block")
            script_spec_block = spec_aliases.get(script_spec_block, script_spec_block)
            script_spec_block_fullname = f"{spec_name}#{script_spec_block}"
            new_script = await Script.create_row(
                session,
                parent_level=element.level,
                spec_block_name=script_spec_block_fullname,
                parent_name=element.fullname,
                name=script_name,
                **script_vals,
            )
            await session.refresh(new_script)
            script_ids_dict[script_name] = new_script.id
            for prereq_ in script_vals.get("prerequisites", []):
                prereq_pairs.append((script_name, prereq_))

        for depend_name, prereq_name in prereq_pairs:
            prereq_id = script_ids_dict[prereq_name]
            depend_id = script_ids_dict[depend_name]
            new_depend = await self._add_prerequisite(session, depend_id, prereq_id)
            await session.refresh(new_depend)

        await element.update_values(session, status=StatusEnum.prepared)
        await session.commit()
        return StatusEnum.prepared

    async def continue_processing(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Continue `Element` processing

        This means processing the scripts associated to this element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        scripts = await element.get_scripts(session, remaining_only=True)
        if scripts:
            for script_ in scripts:
                await script_.process(session, **kwargs)
        await element.update_values(session, status=StatusEnum.running)
        await session.commit()
        return StatusEnum.running

    async def review(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Review a `Element` processing

        By default this does nothing, but
        can be used to automate checking
        that the element is ok

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            Element in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        return element.status

    async def _run_script_checks(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> None:
        """Explicitly check on Scripts associated to this Element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Keywords
        --------
        force_check : bool
            If True check all scripts, not only remaining ones

        fake_status = StatusEnum | None
            If present, set the Status of the scripts to this value
        """
        scripts = await element.get_scripts(session, remaining_only=not kwargs.get("force_check", False))
        fake_status = kwargs.get("fake_status")
        for script_ in scripts:
            if fake_status and script_.status.value >= StatusEnum.prepared.value:
                await script_.update_values(session, status=fake_status)
            await script_.run_check(session)

    async def _run_job_checks(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> None:
        """Explicitly check on Jobs associated to this Element

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Keywords
        --------
        force_check : bool
            If True check all jobs, not only remaining ones

        fake_status = StatusEnum | None
            If present, set the Status of the scripts to this value
        """
        jobs = await element.get_jobs(session, remaining_only=not kwargs.get("force_check", False))
        fake_status = kwargs.get("fake_status")
        for job_ in jobs:
            if fake_status and job_.status.value >= StatusEnum.prepared.value:
                await job_.update_values(session, status=fake_status)
            else:
                await job_.run_check(session)

    async def check(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Check the status of this Element based on the
        status of the associated scripts and jobs

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Keywords
        --------
        do_checks: bool
            If True, explicitly run checks on status of jobs and scripts

        force_check : bool
            If True check all jobs and scripts, not only remaining ones

        fake_status = StatusEnum | None
            If present, set the Status of the scripts to this value
        """
        if kwargs.get("do_checks", False):
            await self._run_script_checks(session, element, **kwargs)
            await self._run_job_checks(session, element, **kwargs)

        scripts = await element.get_scripts(session, remaining_only=True)
        for script_ in scripts:
            if script_.status.value <= StatusEnum.accepted.value:
                status = StatusEnum.running  # FIXME
                await element.update_values(session, status=status)
                await session.commit()
                return status

        status = StatusEnum.accepted
        await element.update_values(session, status=status)
        await session.commit()
        return status
