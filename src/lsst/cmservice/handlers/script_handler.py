from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import async_scoped_session

from ..common.bash import check_stamp_file, get_diagnostic_message, run_bash_job
from ..common.enums import ErrorSourceEnum, ScriptMethodEnum, StatusEnum
from ..common.errors import (
    CMBadExecutionMethodError,
    CMBadStateTransitionError,
    CMBashSubmitError,
    CMHTCondorCheckError,
    CMHTCondorSubmitError,
    CMMissingNodeUrlError,
    CMMissingScriptInputError,
    CMSlurmCheckError,
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
                    diagnostic_message=str(msg),
                )
                status = StatusEnum.failed
        if status == StatusEnum.prepared:
            try:
                status = await self.launch(session, node, parent, **kwargs)
            except (
                CMBadExecutionMethodError,
                CMMissingNodeUrlError,
            ) as msg:  # pragma: no cover
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=str(msg),
                )
                status = StatusEnum.failed
            except (
                CMHTCondorSubmitError,
                CMSlurmSubmitError,
                CMBashSubmitError,
            ) as msg:  # pragma: no cover
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.local_script,
                    diagnostic_message=str(msg),
                )
                status = StatusEnum.failed
        if status == StatusEnum.running:
            try:
                status = await self.check(session, node, parent, **kwargs)
            except (CMBadExecutionMethodError, CMMissingNodeUrlError) as msg:  # pragma: no cover
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=str(msg),
                )
                status = StatusEnum.failed
            except (
                CMHTCondorCheckError,
                CMSlurmCheckError,
            ) as msg:  # pragma: no cover
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.local_script,
                    diagnostic_message=str(msg),
                )
                status = StatusEnum.failed

        if status == StatusEnum.reviewable:
            status = await self.review_script(session, node, parent, **kwargs)
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

    async def review_script(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
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
        fake_status = kwargs.get("fake_status", None)
        return script.status if fake_status is None else fake_status

    async def reset_script(
        self,
        session: async_scoped_session,
        node: NodeMixin,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
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

        update_fields = await self._reset_script(session, node, to_status, fake_reset=fake_reset)
        await node.update_values(session, **update_fields)
        await session.refresh(node, attribute_names=["status"])
        return node.status

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self)}._reset_script()")

    async def _purge_products(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        pass


class ScriptHandler(BaseScriptHandler):
    """SubClass of Handler to deal with script operations using real scripts"""

    default_method = ScriptMethodEnum.htcondor

    @staticmethod
    async def _check_stamp_file(  # pylint: disable=unused-argument
        session: async_scoped_session,
        stamp_file: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Get `Script` status from a stamp file

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        stamp_file: str | None
            File with just the `Script` status written to it

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        fake_status: StatusEnum | None,
            If set, don't actually check the job, set status to fake_status

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        default_status = script.status if fake_status is None else fake_status
        status = check_stamp_file(stamp_file, default_status)
        await script.update_values(session, status=status)
        return status

    async def _check_slurm_job(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        slurm_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
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

        fake_status: StatusEnum | None,
            If set, don't actually check the job, set status to fake_status

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = check_slurm_job(slurm_id, fake_status)
        await script.update_values(session, status=status)
        return status

    async def _check_htcondor_job(  # pylint: disable=unused-argument
        self,
        session: async_scoped_session,
        htcondor_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Check the status of a `Script` sent to htcondor

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        htcondor_id : str | None
            HTCondor job id, in this case the glob from the submission script

        script: Script
            The `Script` in question

        parent: ElementMixin
            Parent Element of the `Script` in question

        fake_status: StatusEnum | None,
            If set, don't actually check the job, set status to fake_status

        Returns
        -------
        status : StatusEnum
            The status of the processing
        """
        status = check_htcondor_job(htcondor_id, fake_status)
        await script.update_values(session, status=status)
        return status

    async def prepare(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = self.default_method if script.method == ScriptMethodEnum.default else script.method

        status = script.status
        if script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
        if script_method == ScriptMethodEnum.bash:
            status = await self._write_script(session, script, parent, **kwargs)
        elif script_method == ScriptMethodEnum.slurm:
            status = await self._write_script(session, script, parent, **kwargs)
        elif script_method == ScriptMethodEnum.htcondor:
            status = await self._write_script(session, script, parent, **kwargs)
        else:  # pragma: no cover
            raise CMBadExecutionMethodError(f"Bad script method {script_method}")
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

        if script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
        if not script.script_url:  # pragma: no cover
            raise CMMissingNodeUrlError(f"script_url is not set for {script}")
        if not script.log_url:  # pragma: no cover
            raise CMMissingNodeUrlError(f"log_url is not set for {script}")

        if script_method == ScriptMethodEnum.bash:
            if not script.stamp_url:  # pragma: no cover
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            run_bash_job(script.script_url, script.log_url, script.stamp_url, **kwargs)
            status = StatusEnum.running
            await script.update_values(session, status=status)
        elif script_method == ScriptMethodEnum.slurm:
            job_id = submit_slurm_job(script.script_url, script.log_url, **kwargs)
            status = StatusEnum.running
            await script.update_values(session, stamp_url=job_id, status=status)
        elif script_method == ScriptMethodEnum.htcondor:
            job_id_base = os.path.abspath(os.path.splitext(script.script_url)[0])
            htcondor_script_path = f"{job_id_base}.sub"
            htcondor_log = f"{job_id_base}.condorlog"
            htcondor_sublog = f"{job_id_base}_condorsub.log"
            write_htcondor_script(
                htcondor_script_path,
                htcondor_log,
                os.path.abspath(script.script_url),
                os.path.abspath(htcondor_sublog),
            )
            submit_htcondor_job(htcondor_script_path, **kwargs)
            status = StatusEnum.running
            await script.update_values(session, stamp_url=htcondor_log, status=status)
        else:  # pragma: no cover
            raise CMBadExecutionMethodError(f"Method {script_method} not valid for {script}")
        await script.update_values(session, status=status)
        return status

    async def check(
        self,
        session: async_scoped_session,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        fake_status = kwargs.get("fake_status", None)

        script_method = self.default_method if script.method == ScriptMethodEnum.default else script.method

        if script_method == ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")

        if script_method == ScriptMethodEnum.bash:
            status = await self._check_stamp_file(session, script.stamp_url, script, parent, fake_status)
        elif script_method == ScriptMethodEnum.slurm:
            status = await self._check_slurm_job(session, script.stamp_url, script, parent, fake_status)
        elif script_method == ScriptMethodEnum.htcondor:
            status = await self._check_htcondor_job(session, script.stamp_url, script, parent, fake_status)
        else:  # pragma: no cover
            raise CMBadExecutionMethodError(f"Bad script method {script_method}")
        if fake_status is not None:
            status = fake_status
        if status == StatusEnum.failed:
            if not script.log_url:  # pragma: no cover
                raise CMMissingNodeUrlError(f"log_url is not set for {script}")
            diagnostic_message = await get_diagnostic_message(script.log_url)
            _new_error = await ScriptError.create_row(
                session,
                script_id=script.id,
                source=ErrorSourceEnum.local_script,
                diagnostic_message=diagnostic_message,
            )
        if status != script.status:
            await script.update_values(session, status=status)
        return status

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
        stamp_url = f"{prod_area}/{script.fullname}.stamp"
        await script.update_values(session, script_url=script_url, log_url=log_url, stamp_url=stamp_url)
        return script_url

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields: dict[str, Any] = {}
        if to_status.value <= StatusEnum.prepared.value:
            update_fields["stamp_url"] = None
            if script.log_url and os.path.exists(script.log_url):  # pragma: no cover
                os.unlink(script.log_url)
            if script.stamp_url and os.path.exists(script.stamp_url):
                os.unlink(script.stamp_url)
        if to_status.value <= StatusEnum.ready.value:
            if script.script_url:
                os.unlink(script.script_url)
            update_fields["script_url"] = None
            update_fields["log_url"] = None
        update_fields["status"] = to_status
        await self._purge_products(session, script, to_status, fake_reset=fake_reset)
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
        if script_method != ScriptMethodEnum.no_script:  # pragma: no cover
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

        if script_method != ScriptMethodEnum.no_script:  # pragma: no cover
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

        if script_method != ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_check(session, script, parent, **kwargs)
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
        raise NotImplementedError

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
        raise NotImplementedError

    async def _reset_script(
        self,
        session: async_scoped_session,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields = {}
        update_fields["status"] = to_status
        await self._purge_products(session, script, to_status, fake_reset=fake_reset)
        return update_fields
