from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMYamlParseError, test_type_and_raise
from ..config import config
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
            changed |= has_changed
        if status == StatusEnum.prepared:
            (has_changed, status) = await self.continue_processing(session, node, **kwargs)
            changed |= has_changed
        if status == StatusEnum.running:
            (has_changed, status) = await self.check(session, node, **kwargs)
            changed |= has_changed
            if status == StatusEnum.running:
                (has_changed, status) = await self.continue_processing(session, node, **kwargs)
                changed |= has_changed
        if status == StatusEnum.reviewable:
            status = await self.review(session, node, **kwargs)
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

        script_ids_dict = {}
        prereq_pairs = []
        if TYPE_CHECKING:
            assert isinstance(spec_block.scripts, Iterable)
        for script_item in spec_block.scripts:
            try:
                script_vals = script_item["Script"].copy()
            except KeyError as msg:
                raise CMYamlParseError(f"Expected Script tag, found {script_item.keys()}") from msg
            test_type_and_raise(script_vals, dict, "ElementHandler Script yaml tag")
            try:
                script_name = script_vals.pop("name")
            except KeyError as msg:
                raise CMYamlParseError(f"Unnnamed Script block {script_vals}") from msg
            script_spec_block_name = script_vals.get("spec_block", None)
            if script_spec_block_name is None:  # pragma: no cover
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
    ) -> StatusEnum:
        """Review a `Element` processing

        By default this accepts the element but
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
            Status of the processing
        """
        fake_status = kwargs.get("fake_status", None)
        status = fake_status if fake_status is not None else StatusEnum.accepted
        return status

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
            script_changed, _script_status = await script_.run_check(session, fake_status=fake_status)
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
            (job_changed, _job_status) = await job_.run_check(session, fake_status=fake_status)
            changed |= job_changed
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
            changed |= scripts_changed or jobs_changed

        remaining_only = not kwargs.get("force_check", False)
        status = StatusEnum.accepted
        scripts = await element.get_scripts(session, remaining_only=remaining_only)
        for script_ in scripts:
            status = StatusEnum(min(status.value, script_.status.value))

        if element.level != LevelEnum.job:
            jobs = await element.get_jobs(session, remaining_only=remaining_only)
        else:
            jobs = []
        for job_ in jobs:
            status = StatusEnum(min(status.value, job_.status.value))

        # Keep this around until we've determined if we need a special
        # way to handle reviewable state when doing fake runs
        # if status == StatusEnum.reviewable:
        #    if kwargs.get('fake_status', StatusEnum.reviewable).value
        #       > StatusEnum.reviewable.value:
        #        _, status = await self.review(session, element, **kwargs)
        if status.value < StatusEnum.accepted.value:
            status = StatusEnum.running
            await element.update_values(session, status=status)
            return (changed, status)

        status = await self._post_check(session, element, **kwargs)
        fake_status = kwargs.get("fake_status", config.mock_status)
        if fake_status:
            status = fake_status
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
