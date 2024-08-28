from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMYamlParseError
from ..db.campaign import Campaign
from ..db.element import ElementMixin
from ..db.handler import Handler
from ..db.node import NodeMixin
from ..db.script import Script
from ..db.script_dependency import ScriptDependency
from .functions import add_steps


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
        # await session.refresh(new_depend)
        return new_depend

    async def process(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
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
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        status = node.status
        orig_status = node.status
        changed = False
        has_changed = False
        # Need this so mypy doesn't think we are passing in Script
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)  # for mypy
        if status == StatusEnum.waiting:
            is_ready = await node.check_prerequisites(session)
            if is_ready:
                status = StatusEnum.ready
                changed = True
        if status == StatusEnum.ready:
            (has_changed, status) = await self.prepare(session, node)
            if has_changed:
                changed = True
        if status == StatusEnum.prepared:
            (has_changed, status) = await self.continue_processing(session, node, **kwargs)
            if has_changed:
                changed = True
        if status == StatusEnum.running:
            (has_changed, status) = await self.check(session, node, **kwargs)
            if has_changed:
                changed = True
            if status == StatusEnum.running:
                (has_changed, status) = await self.continue_processing(session, node, **kwargs)
                if has_changed:
                    changed = True
        if status == StatusEnum.reviewable:
            (has_changed, status) = await self.review(session, node, *kwargs)
            if has_changed:
                changed = True
        if status != orig_status:
            changed = True
            await node.update_values(session, status=status)
        return (changed, status)

    async def run_check(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        # Need this so mypy doesn't think we are passing in Script
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)  # for mypy
        return await self.check(session, node, **kwargs)

    async def prepare(
        self,
        session: async_scoped_session,
        element: ElementMixin,
    ) -> tuple[bool, StatusEnum]:
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
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        spec_block = await element.get_spec_block(session)
        spec_aliases = await element.get_spec_aliases(session)
        if not spec_block.scripts:
            return (True, StatusEnum.prepared)

        script_ids_dict = {}
        prereq_pairs = []
        for script_item in spec_block.scripts:
            try:
                script_vals = script_item["Script"].copy()
            except KeyError as msg:
                raise CMYamlParseError(f"Expected Script tag, found {script_item.keys()}") from msg
            if not isinstance(script_vals, dict):
                raise CMYamlParseError(f"Script Tag should be a dict not {script_vals}")
            try:
                script_name = script_vals.pop("name")
            except KeyError as msg:
                raise CMYamlParseError(f"Unnnamed Script block {script_vals}") from msg
            script_spec_block_name = script_vals.get("spec_block", None)
            if script_spec_block_name is None:
                raise CMYamlParseError(f"Script block {script_name} does not contain spec_block")
            script_spec_block_name = spec_aliases.get(script_spec_block_name, script_spec_block_name)
            new_script = await Script.create_row(
                session,
                parent_level=element.level,
                spec_block_name=script_spec_block_name,
                parent_name=element.fullname,
                name=script_name,
                **script_vals,
            )
            await session.refresh(new_script, attribute_names=["id"])
            script_ids_dict[script_name] = new_script.id
            prereq_pairs += [(script_name, prereq_) for prereq_ in script_vals.get("prerequisites", [])]

        for depend_name, prereq_name in prereq_pairs:
            prereq_id = script_ids_dict[prereq_name]
            depend_id = script_ids_dict[depend_name]
            _new_depend = await self._add_prerequisite(session, depend_id, prereq_id)
            # await session.refresh(new_depend)

        await element.update_values(session, status=StatusEnum.prepared)
        return (True, StatusEnum.prepared)

    async def continue_processing(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
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
        chagned : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        scripts = await element.get_scripts(session, remaining_only=True)
        changed = False
        if scripts:
            for script_ in scripts:
                (script_changed, _script_status) = await script_.process(session, **kwargs)
                if script_changed:
                    await script_.update_values(session, status=_script_status)
                    changed = True
        await element.update_values(session, status=StatusEnum.running)
        return (changed, StatusEnum.running)

    async def review(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
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
        chagned : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        return (False, element.status)

    async def _run_script_checks(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> bool:
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

        Returns
        -------
        changed : bool
            True if anything has changed
        """
        scripts = await element.get_scripts(session, remaining_only=not kwargs.get("force_check", False))
        fake_status = kwargs.get("fake_status", None)
        changed = False
        for script_ in scripts:
            if fake_status and script_.status.value >= StatusEnum.prepared.value:
                await script_.update_values(session, status=fake_status)
                changed = True
            script_changed, _script_status = await script_.run_check(session)
            if script_changed:
                changed = True
        return changed

    async def _run_job_checks(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> bool:
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

        Returns
        -------
        changed : bool
            True if anything has changed
        """
        jobs = await element.get_jobs(session, remaining_only=not kwargs.get("force_check", False))
        fake_status = kwargs.get("fake_status")
        changed = False
        for job_ in jobs:
            if fake_status and job_.status.value >= StatusEnum.prepared.value:
                await job_.update_values(session, status=fake_status)
                changed = True
            else:
                (job_changed, _job_status) = await job_.run_check(session)
                if job_changed:
                    changed = True
        return changed

    async def check(
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
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

        Returns
        -------
        changed : bool
            True if anything has changed
        status : StatusEnum
            Status of the processing
        """
        changed = False
        if kwargs.get("do_checks", False):
            scripts_changed = await self._run_script_checks(session, element, **kwargs)
            jobs_changed = await self._run_job_checks(session, element, **kwargs)
            if scripts_changed or jobs_changed:
                changed = True

        scripts = await element.get_scripts(session, remaining_only=True)
        for script_ in scripts:
            if script_.status.value <= StatusEnum.accepted.value:
                status = StatusEnum.running  # FIXME
                await element.update_values(session, status=status)
                return (changed, status)

        if element.level != LevelEnum.job:
            jobs = await element.get_jobs(session, remaining_only=True)
        else:
            jobs = []
        for job_ in jobs:
            if job_.status.value <= StatusEnum.accepted.value:
                status = StatusEnum.running  # FIXME, revisit someday
                await element.update_values(session, status=status)
                return (changed, status)

        status = await self._post_check(session, element, **kwargs)
        status = StatusEnum.accepted
        await element.update_values(session, status=status)
        return (True, status)

    async def _post_check(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        element: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for a final check after all the scripts have run

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        element: ElementMixin
            `Element` in question

        Returns
        -------
        status : StatusEnum
            Status of the processing
        """
        return StatusEnum.accepted


class CampaignHandler(ElementHandler):
    """SubClass of Handler to deal with Campaign operations,"""

    async def prepare(
        self,
        session: async_scoped_session,
        element: ElementMixin,
    ) -> tuple[bool, StatusEnum]:
        if TYPE_CHECKING:
            assert isinstance(element, Campaign)  # for mypy

        spec_block = await element.get_spec_block(session)
        child_configs = spec_block.steps
        if TYPE_CHECKING:
            assert isinstance(child_configs, list)
        await add_steps(session, element, child_configs)
        return await ElementHandler.prepare(self, session, element)
