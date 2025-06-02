from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.enums import LevelEnum, StatusEnum
from ..common.errors import CMYamlParseError, test_type_and_raise
from ..common.notification import send_notification
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
        namespace: UUID | None = None,
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
            namespace=namespace,
        )
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
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)
        if status is StatusEnum.waiting:
            is_ready = await node.check_prerequisites(session)
            if is_ready:
                status = StatusEnum.ready
                changed = True
        if status is StatusEnum.ready:
            (has_changed, status) = await self.prepare(session, node)
            changed |= has_changed
        if status is StatusEnum.prepared:
            (has_changed, status) = await self.continue_processing(session, node, **kwargs)
            changed |= has_changed
        if status is StatusEnum.running:
            (has_changed, status) = await self.check(session, node, **kwargs)
            changed |= has_changed
            if status is StatusEnum.running:
                (has_changed, status) = await self.continue_processing(session, node, **kwargs)
                changed |= has_changed
        if status is StatusEnum.reviewable:
            # TODO put notification here instead of in review()?
            status = await self.review(session, node, **kwargs)
        if status is not orig_status:
            changed = True
            await node.update_values(session, status=status)
        return (changed, status)

    async def run_check(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        if TYPE_CHECKING:
            assert isinstance(node, ElementMixin)  # for mypy
        return await self.check(session, node, **kwargs)

    async def prepare(
        self,
        session: async_scoped_session,
        element: ElementMixin,
    ) -> tuple[bool, StatusEnum]:
        """Prepare `Element` for processing

        Creates database entries for scripts and their inter-dependencies

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
        element_campaign = await element.get_campaign(session)
        spec_block = await element.get_spec_block(session)
        spec_aliases = await element.get_spec_aliases(session)

        script_ids_dict = {}
        prereq_pairs = []
        if TYPE_CHECKING:
            assert isinstance(spec_block.scripts, Iterable)
            assert isinstance(element_campaign.data, dict)

        if element_campaign.data.get("namespace"):
            campaign_namespace = UUID(element_campaign.data.get("namespace"))
        else:
            campaign_namespace = None

        # Campaigns, Steps, Groups, and Jobs may have Scripts
        for script_item in spec_block.scripts:
            try:
                script_vals = script_item["Script"].copy()
            except KeyError as msg:
                raise CMYamlParseError(f"Expected Script tag, found {script_item.keys()}") from msg
            test_type_and_raise(script_vals, dict, "ElementHandler Script yaml tag")
            try:
                script_name = script_vals.pop("name")
                namespaced_script_name = (
                    str(uuid5(campaign_namespace, script_name)) if campaign_namespace else script_name
                )
            except KeyError as msg:
                raise CMYamlParseError(f"Unnnamed Script block {script_vals}") from msg

            script_spec_block_name = script_vals.get("spec_block", None)
            if script_spec_block_name is None:  # pragma: no cover
                raise CMYamlParseError(f"Script block {script_name} does not contain spec_block")

            # If the spec_aliases does not have a key for the current script
            # name, then it is not an alias.
            if (script_spec_block_name in spec_aliases) or (not campaign_namespace):
                script_spec_block_name = spec_aliases.get(script_spec_block_name, script_spec_block_name)
            else:
                # generate a namespaced name from the current campaign
                script_spec_block_name = str(uuid5(campaign_namespace, script_spec_block_name))

            new_script = await Script.create_row(
                session,
                parent_level=element.level,
                spec_block_name=script_spec_block_name,
                parent_name=element.fullname,
                name=namespaced_script_name,
                original_name=script_name,
                **script_vals,
            )
            await session.refresh(new_script, attribute_names=["id"])
            script_ids_dict[namespaced_script_name] = new_script.id

            prereq_list = [
                str(uuid5(campaign_namespace, prereq)) if campaign_namespace else prereq
                for prereq in script_vals.get("prerequisites", [])
            ]
            prereq_pairs += [(namespaced_script_name, prereq) for prereq in prereq_list]

        for depend_name, prereq_name in prereq_pairs:
            prereq_id = script_ids_dict[prereq_name]
            depend_id = script_ids_dict[depend_name]
            _ = await self._add_prerequisite(session, depend_id, prereq_id, namespace=campaign_namespace)

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

    async def review(
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

    async def _post_check(
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
            assert isinstance(element, Campaign)

        spec_block = await element.get_spec_block(session)
        child_configs = spec_block.steps
        if TYPE_CHECKING:
            assert isinstance(child_configs, list)
        await add_steps(session, element, child_configs)
        await send_notification(for_status=StatusEnum.running, for_campaign=element)
        return await ElementHandler.prepare(self, session, element)

    async def _post_check(
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
        if TYPE_CHECKING:
            assert isinstance(element, Campaign)
        status = StatusEnum.accepted
        await send_notification(for_status=status, for_campaign=element)
        return status
