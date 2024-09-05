from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.bash import check_stamp_file, run_bash_job
from ..common.enums import ErrorSourceEnum, ScriptMethodEnum, StatusEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadStateTransitionError,
    CMBashSubmitError,
    CMHTCondorSubmitError,
    CMMissingNodeUrlError,
    CMMissingScriptInputError,
    CMSlurmSubmitError,
)
from ..common.htcondor import check_htcondor_job, submit_htcondor_job, write_htcondor_script
from ..common.slurm import check_slurm_job, submit_slurm_job
from ..db.element import ElementMixin
from ..db.handler import Handler
from ..db.node import NodeMixin
from ..db.script import Script
from ..db.script_error import ScriptError


class BaseScriptHandler(Handler):
    """SubClass of Handler to deal with script operations"""

    async def process(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        # Need this so mypy doesn't think we are passing in Element
        if TYPE_CHECKING:
            assert isinstance(node, Script)  # for mypy
        orig_status = node.status
        status = node.status
        changed = False
        if status == StatusEnum.waiting:
            is_ready = await node.check_prerequisites(session)
            if is_ready:
                status = StatusEnum.ready
        parent = await node.get_parent(session)
        if status == StatusEnum.ready:
            try:
                status = await self.prepare(session, node, parent, **kwargs)
            except (CMBadExecutionMethodError, CMMissingScriptInputError) as msg:
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=msg,
                )
                status = StatusEnum.failed
        if status == StatusEnum.prepared:
            try:
                status = await self.launch(session, node, parent, **kwargs)
            except (
                CMBadExecutionMethodError,
                CMMissingNodeUrlError,
                CMHTCondorSubmitError,
                CMSlurmSubmitError,
                CMBashSubmitError,
            ) as msg:
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=msg,
                )
                status = StatusEnum.failed
        if status == StatusEnum.running:
            try:
                status = await self.check(session, node, parent, **kwargs)
            except (CMBadExecutionMethodError, CMMissingNodeUrlError) as msg:
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=msg,
                )
                status = StatusEnum.failed
        if status == StatusEnum.reviewable:
            status = await self.review(session, node, parent)
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
        # Need this so mypy doesn't think we are passing in Element
        if TYPE_CHECKING:
            assert isinstance(node, Script)  # for mypy
        parent = await node.get_parent(session)
        orig_status = node.status
        changed = False
        status = await self.check(session, node, parent, **kwargs)
        if orig_status != status:
            changed = True
        return (changed, status)

    async def prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Prepare `Script` for processing

        Depending on the script this could either mean writing (but not
        running) the script, or creating (but not processing) database
        rows for child elements

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        kwargs: Any
            Used to override processing configuration

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        raise NotImplementedError("{type(self)}.prepare()")

    async def launch(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Launch a `Script` processing

        Depending on the script this could either mean running
        an existing the script, or processing database
        rows for child elements

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        raise NotImplementedError("{type(self)}.launch()")

    async def check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Check on a `Script` processing

        Depending on the script this could mean aksing
        slurm about job status, or checking the processing
        status of child scripts, or looking for a stamp file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        raise NotImplementedError("{type(self)}.check()")

    async def review(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Review a `Script` processing

        By default this does nothing, but
        can be used to automate checking
        jobs that a script has launched
        or validating outputs or other
        review-like actions

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        return script.status

    async def reset_script(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        to_status: StatusEnum,
    ) -> StatusEnum:
        if TYPE_CHECKING:
            assert isinstance(node, Script)  # for mypy

        valid_states = [StatusEnum.waiting, StatusEnum.ready, StatusEnum.prepared]
        if to_status not in valid_states:
            raise CMBadStateTransitionError(
                f"script.reset to_status should be in {valid_states}, not: {to_status}",
            )

        if to_status.value >= node.status.value and not node.status.is_bad():
            raise CMBadStateTransitionError(
                f"Current status of {node.status} is less advanced than {to_status}",
            )

        if node.status.value >= StatusEnum.running.value:
            raise CMBadStateTransitionError(
                f"Can not use script.reset on script in {node.status}.  "
                "Use script.rollback or script.retry instead",
            )

        update_fields = await self._reset_script(session, node, to_status)
        await node.update_values(session, **update_fields)
        await session.refresh(node, attribute_names=["status"])
        return node.status

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self)}._reset_script()")

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> None:
        pass


class ScriptHandler(BaseScriptHandler):
    """SubClass of Handler to deal with script operations using real scripts"""

    default_method = ScriptMethodEnum.htcondor

    @staticmethod
    async def _check_stamp_file(  # pylint: disable=unused-argument
        session: async_scoped_session,
        stamp_file: str,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Get `Script` status from a stamp file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        stamp_file: str
            File with just the `Script` status written to it

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = await check_stamp_file(stamp_file)
        if status is None:
            return script.status
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def _check_slurm_job(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        slurm_id: str | None,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Check the status of a `Script` sent to slurm

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        slurm_id : str
            Slurm job id

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = await check_slurm_job(slurm_id)
        print(f"Getting status for {script.fullname} {status}")
        if status is None:
            status = StatusEnum.running
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def _check_htcondor_job(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        htcondor_id: str | None,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Check the status of a `Script` sent to htcondor

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        htcondor_id : str
            HTCondor job id

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = await check_htcondor_job(htcondor_id)
        print(f"Getting status for {script.fullname} {status}")
        if status is None:
            status = StatusEnum.running
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method == ScriptMethodEnum.default:
            script_method = self.default_method

        status = script.status
        if script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
        if script_method == ScriptMethodEnum.bash:
            status = await self._write_script(session, script, parent, **kwargs)
        elif script_method == ScriptMethodEnum.slurm:  # pragma: no cover
            status = await self._write_script(session, script, parent, **kwargs)
        elif script_method == ScriptMethodEnum.htcondor:  # pragma: no cover
            status = await self._write_script(session, script, parent, **kwargs)
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def launch(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method == ScriptMethodEnum.default:
            script_method = self.default_method

        fake_status = kwargs.get("fake_status", None)
        if script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
        orig_status = script.status
        if fake_status:
            status = fake_status
        elif script_method == ScriptMethodEnum.bash:
            if not script.script_url:
                raise CMMissingNodeUrlError(f"script_url is not set for {script}")
            if not script.log_url:
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            await run_bash_job(script.script_url, script.log_url)
            status = StatusEnum.running
        elif script_method == ScriptMethodEnum.slurm:  # pragma: no cover
            if not script.script_url:
                raise CMMissingNodeUrlError(f"script_url is not set for {script}")
            if not script.log_url:
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            job_id = await submit_slurm_job(script.script_url, script.log_url)
            status = StatusEnum.running
            await script.update_values(session, stamp_url=job_id, status=status)
        elif script_method == ScriptMethodEnum.htcondor:  # pragma: no cover
            if not script.script_url:
                raise CMMissingNodeUrlError(f"script_url is not set for {script}")
            if not script.log_url:
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            job_id_base = os.path.abspath(os.path.splitext(script.script_url)[0])
            htcondor_script = f"{job_id_base}.sub"
            htcondor_log = f"{job_id_base}.condorlog"
            await write_htcondor_script(
                htcondor_script,
                htcondor_log,
                os.path.abspath(script.script_url),
                os.path.abspath(script.log_url),
            )
            await submit_htcondor_job(htcondor_script)
            status = StatusEnum.running
            await script.update_values(session, stamp_url=htcondor_log, status=status)
        else:
            raise CMBadExecutionMethodError(f"Method {script_method} not valid for {script}")
        if status != orig_status:
            await script.update_values(session, status=status)
        return status

    async def check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method == ScriptMethodEnum.default:
            script_method = self.default_method

        fake_status = kwargs.get("fake_status")
        if fake_status:
            status = fake_status
        elif script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
        elif script_method == ScriptMethodEnum.bash:
            if not script.stamp_url:
                raise CMMissingNodeUrlError(f"stamp_url is not set for {script}")
            status = await self._check_stamp_file(session, script.stamp_url, script, parent)
        elif script_method == ScriptMethodEnum.slurm:  # pragma: no cover
            if not script.stamp_url:
                raise CMMissingNodeUrlError(f"stamp_url is not set for {script}")
            status = await self._check_slurm_job(session, script.stamp_url, script, parent)
        elif script_method == ScriptMethodEnum.htcondor:  # pragma: no cover
            if not script.stamp_url:
                raise CMMissingNodeUrlError(f"stamp_url is not set for {script}")
            status = await self._check_htcondor_job(session, script.stamp_url, script, parent)
        if status == StatusEnum.failed:
            if not script.log_url:
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            diagnostic_message = await self._get_diagnostic_message(script.log_url)
            _new_error = await ScriptError.create_row(
                session,
                script_id=script.id,
                source=ErrorSourceEnum.local_script,
                diagnostic_message=diagnostic_message,
            )
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def _get_diagnostic_message(
        self,
        log_url: str,
    ) -> str:
        with open(log_url, encoding="utf-8") as fin:
            lines = fin.readlines()
            if lines:
                return lines[-1]
            return "Empty log file"

    async def _write_script(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to write a script for processing

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        raise NotImplementedError(f"{type(self)}.write_script()")

    async def _set_script_files(
        self,
        session: async_scoped_session,
        script: Script,
        prod_area: str,
    ) -> str:
        script_url = f"{prod_area}/{script.fullname}.sh"
        log_url = f"{prod_area}/{script.fullname}.log"
        await script.update_values(session, script_url=script_url, log_url=log_url)
        return script_url

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> dict[str, Any]:
        update_fields: dict[str, Any] = {}
        if to_status.value <= StatusEnum.prepared.value:
            update_fields["stamp_url"] = None
            if script.log_url:
                os.unlink(script.log_url)
        if to_status.value <= StatusEnum.ready.value:
            if script.script_url:
                os.unlink(script.script_url)
            update_fields["script_url"] = None
            update_fields["log_url"] = None
        update_fields["status"] = to_status
        await self._purge_products(session, script, to_status)
        return update_fields


class FunctionHandler(BaseScriptHandler):
    """SubClass of Handler for scripts that are actually python functions"""

    default_method = ScriptMethodEnum.no_script

    async def prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method is ScriptMethodEnum.default:
            script_method = self.default_method
        if script_method != ScriptMethodEnum.no_script:
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_prepare(session, script, parent, **kwargs)
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def launch(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method == ScriptMethodEnum.default:
            script_method = self.default_method

        if script_method != ScriptMethodEnum.no_script:
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_run(session, script, parent, **kwargs)
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method == ScriptMethodEnum.default:
            script_method = self.default_method

        if script_method != ScriptMethodEnum.no_script:
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_check(session, script, parent, **kwargs)
        if status != script.status:
            await script.update_values(session, status=status)
        return status

    async def _do_prepare(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to prepare a `Script` for processing

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        return StatusEnum.prepared

    async def _do_run(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to process a `Script`

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        return StatusEnum.running

    async def _do_check(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to check on `Script` processing

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        return StatusEnum.accepted

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
    ) -> dict[str, Any]:
        update_fields = {}
        update_fields["status"] = to_status
        await self._purge_products(session, script, to_status)
        return update_fields
