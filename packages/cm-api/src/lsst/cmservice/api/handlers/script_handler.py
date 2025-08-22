from __future__ import annotations

from typing import TYPE_CHECKING, Any

from anyio import Path

from lsst.cmservice.core.common.bash import check_stamp_file, get_diagnostic_message, run_bash_job
from lsst.cmservice.core.common.enums import ErrorSourceEnum, ScriptMethodEnum, StatusEnum
from lsst.cmservice.core.common.errors import (
    CMBadExecutionMethodError,
    CMBadStateTransitionError,
    CMCheckError,
    CMMissingNodeUrlError,
    CMMissingScriptInputError,
    CMSubmitError,
)
from lsst.cmservice.core.common.htcondor import check_htcondor_job, submit_htcondor_job, write_htcondor_script
from lsst.cmservice.core.common.logging import LOGGER
from lsst.cmservice.core.common.notification import send_notification
from lsst.cmservice.core.common.slurm import check_slurm_job, submit_slurm_job
from lsst.cmservice.core.config import config
from lsst.cmservice.core.db.element import ElementMixin
from lsst.cmservice.core.db.handler import Handler
from lsst.cmservice.core.db.node import NodeMixin
from lsst.cmservice.core.db.script import Script
from lsst.cmservice.core.db.script_error import ScriptError

if TYPE_CHECKING:
    from lsst.cmservice.core.common.types import AnyAsyncSession


logger = LOGGER.bind(module=__name__)

DOUBLE_QUOTE = '"'


class BaseScriptHandler(Handler):
    """SubClass of Handler to deal with script operations"""

    async def process(
        self,
        session: AnyAsyncSession,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        """Evolve the state of the script through its possible status states.

        It is possible for a single call to this method to evolve the state of
        a script through more than one status.
        """
        if TYPE_CHECKING:
            assert isinstance(node, Script)
        failure_diagnostic_message = None
        orig_status = node.status
        status = node.status
        changed = False
        parent = await node.get_parent(session)
        if status is StatusEnum.waiting:
            is_ready = await node.check_prerequisites(session)
            if is_ready:
                status = StatusEnum.ready
        if status is StatusEnum.ready:
            try:
                status = await self.prepare(session, node, parent, **kwargs)
            except (CMBadExecutionMethodError, CMMissingScriptInputError) as msg:
                failure_diagnostic_message = str(msg).strip(DOUBLE_QUOTE)
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=failure_diagnostic_message,
                )
                status = StatusEnum.failed
        if status is StatusEnum.prepared:
            try:
                status = await self.launch(session, node, parent, **kwargs)
            except (
                CMBadExecutionMethodError,
                CMMissingNodeUrlError,
            ) as msg:  # pragma: no cover
                failure_diagnostic_message = str(msg).strip(DOUBLE_QUOTE)
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=failure_diagnostic_message,
                )
                status = StatusEnum.failed
            except CMSubmitError as msg:  # pragma: no cover
                failure_diagnostic_message = str(msg).strip(DOUBLE_QUOTE)
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.local_script,
                    diagnostic_message=failure_diagnostic_message,
                )
                status = StatusEnum.failed
        if status is StatusEnum.running:
            try:
                status = await self.check(session, node, parent, **kwargs)
            except (CMBadExecutionMethodError, CMMissingNodeUrlError) as msg:  # pragma: no cover
                failure_diagnostic_message = str(msg).strip(DOUBLE_QUOTE)
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.cmservice,
                    diagnostic_message=failure_diagnostic_message,
                )
                status = StatusEnum.failed
            except CMCheckError as msg:  # pragma: no cover
                failure_diagnostic_message = str(msg).strip(DOUBLE_QUOTE)
                _new_error = await ScriptError.create_row(
                    session,
                    script_id=node.id,
                    source=ErrorSourceEnum.local_script,
                    diagnostic_message=failure_diagnostic_message,
                )
                status = StatusEnum.failed
        if status is StatusEnum.reviewable:
            status = await self.review_script(session, node, parent, **kwargs)
        if status is not orig_status:
            changed = True
            await node.update_values(session, status=status)
            await node.update_mtime(session)
            if status in [StatusEnum.failed, StatusEnum.reviewable]:
                campaign = await node.get_campaign(session)
                await send_notification(
                    status, for_campaign=campaign, for_job=node, detail=failure_diagnostic_message
                )

        return (changed, status)

    async def run_check(
        self,
        session: AnyAsyncSession,
        node: NodeMixin,
        **kwargs: Any,
    ) -> tuple[bool, StatusEnum]:
        if TYPE_CHECKING:
            assert isinstance(node, Script)
        parent = await node.get_parent(session)
        orig_status = node.status
        changed = False
        status = await self.check(session, node, parent, **kwargs)
        if orig_status is not status:
            changed = True
        return (changed, status)

    async def prepare(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
    ) -> StatusEnum:
        """Prepare `Script` for processing

        Depending on the script this could either mean writing (but not
        running) the script, or creating (but not processing) database
        rows for child elements

        Parameters
        ----------
        session : AnyAsyncSession
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
        session: AnyAsyncSession,
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
        session : AnyAsyncSession
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
        session: AnyAsyncSession,
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
        session : AnyAsyncSession
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

    async def review_script(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Review a `Script` processing

        By default this does nothing, but can be used to automate checking
        jobs that a script has launched or validating outputs or other
        review-like actions

        Parameters
        ----------
        session : AnyAsyncSession
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
        fake_status = kwargs.get("fake_status", config.mock_status)
        return script.status if fake_status is None else fake_status

    async def reset_script(
        self,
        session: AnyAsyncSession,
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
        session: AnyAsyncSession,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self)}._reset_script()")

    async def _purge_products(
        self,
        session: AnyAsyncSession,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> None:
        pass

    async def update_status(
        self,
        session: AnyAsyncSession,
        status: StatusEnum,
        node: NodeMixin,
        **kwargs: Any,
    ) -> None:
        ...
        """Update the status of a Script.

        If the new status is not a changed status, no action is taken. If the
        status is new, the mtime of the script and all its parents is updated.

        If the status is terminal, the status is bubbled up to all its parents
        and a notification is sent.
        """
        # TODO implement a single method for handling all status update
        #      behaviors.
        raise NotImplementedError


class ScriptHandler(BaseScriptHandler):
    """SubClass of Handler to deal with script operations using real scripts"""

    default_method = config.script_handler
    default_compute_site = config.compute_site

    @staticmethod
    async def _check_stamp_file(
        session: AnyAsyncSession,
        stamp_file: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Get `Script` status from a stamp file

        Parameters
        ----------
        session : AnyAsyncSession
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
        fake_status = fake_status or config.mock_status
        default_status = script.status if fake_status is None else fake_status
        status = await check_stamp_file(stamp_file, default_status)
        await script.update_values(session, status=status)
        return status

    async def _check_slurm_job(
        self,
        session: AnyAsyncSession,
        slurm_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Check the status of a `Script` sent to slurm

        Parameters
        ----------
        session : AnyAsyncSession
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
        status = await check_slurm_job(slurm_id, fake_status)
        await script.update_values(session, status=status)
        return status

    async def _check_htcondor_job(
        self,
        session: AnyAsyncSession,
        htcondor_id: str | None,
        script: Script,
        parent: ElementMixin,
        fake_status: StatusEnum | None = None,
    ) -> StatusEnum:
        """Check the status of a `Script` sent to htcondor

        Parameters
        ----------
        session : AnyAsyncSession
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
        status = await check_htcondor_job(htcondor_id, fake_status)
        await script.update_values(session, status=status)
        return status

    async def prepare(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = self.default_method if script.method is ScriptMethodEnum.default else script.method

        status = script.status
        match script_method:
            case ScriptMethodEnum.no_script:
                raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
            case ScriptMethodEnum.bash:
                status = await self._write_script(session, script, parent, **kwargs)
            case ScriptMethodEnum.slurm:
                status = await self._write_script(session, script, parent, **kwargs)
            case ScriptMethodEnum.htcondor:
                status = await self._write_script(session, script, parent, setup_stack=True, **kwargs)
            case _:
                raise CMBadExecutionMethodError(f"Bad script method {script_method}")
        await script.update_values(session, status=status)
        return status

    async def launch(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method is ScriptMethodEnum.default:
            script_method = self.default_method
        if not script.script_url:  # pragma: no cover
            raise CMMissingNodeUrlError(f"script_url is not set for {script}")
        if not script.log_url:  # pragma: no cover
            raise CMMissingNodeUrlError(f"log_url is not set for {script}")

        match script_method:
            case ScriptMethodEnum.no_script:  # pragma: no cover
                raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
            case ScriptMethodEnum.bash:
                if not script.stamp_url:  # pragma: no cover
                    raise CMMissingNodeUrlError(f"stamp_url is not set for {script}")
                await run_bash_job(script.script_url, script.log_url, script.stamp_url, **kwargs)
                status = StatusEnum.running
                await script.update_values(session, status=status)
            case ScriptMethodEnum.slurm:
                job_id = await submit_slurm_job(script.script_url, script.log_url, **kwargs)
                status = StatusEnum.running
                await script.update_values(session, stamp_url=job_id, status=status)
            case ScriptMethodEnum.htcondor:
                job_script_path = await Path(script.script_url).resolve()
                htcondor_script_path = job_script_path.with_suffix(".sub")
                htcondor_log = job_script_path.with_suffix(".condorlog")
                htcondor_sublog = job_script_path.with_stem(f"{job_script_path.stem}_condorsub").with_suffix(
                    ".log"
                )
                await write_htcondor_script(
                    htcondor_script_path,
                    htcondor_log,
                    script_url=await Path(script.script_url).resolve(),
                    log_url=await Path(htcondor_sublog).resolve(),
                )
                await submit_htcondor_job(htcondor_script_path, **kwargs)
                status = StatusEnum.running
                await script.update_values(session, stamp_url=str(htcondor_log), status=status)
            case _:
                raise CMBadExecutionMethodError(f"Method {script_method} not valid for {script}")
        await script.update_values(session, status=status)
        return status

    async def check(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        fake_status = kwargs.get("fake_status", config.mock_status)
        script_method = self.default_method if script.method is ScriptMethodEnum.default else script.method

        match script_method:
            case ScriptMethodEnum.bash:
                status = await self._check_stamp_file(session, script.stamp_url, script, parent, fake_status)
            case ScriptMethodEnum.slurm:
                status = await self._check_slurm_job(session, script.stamp_url, script, parent, fake_status)
            case ScriptMethodEnum.htcondor:
                status = await self._check_htcondor_job(
                    session, script.stamp_url, script, parent, fake_status
                )
            case ScriptMethodEnum.no_script:
                raise CMBadExecutionMethodError("ScriptMethodEnum.no_script can not be set for ScriptHandler")
            case _:
                raise CMBadExecutionMethodError(f"Bad script method {script_method}")

        if fake_status is not None:
            status = fake_status

        if status is StatusEnum.failed:
            logger.error("Handling failure case for script", script_name=script.fullname)
            if not script.log_url:
                if fake_status is None:  # pragma: no cover
                    raise CMMissingNodeUrlError(f"log_url is not set for {script}")
                diagnostic_message = "Fake failure"
            else:  # pragma: no cover
                diagnostic_message = await get_diagnostic_message(script.log_url)
            _ = await ScriptError.create_row(
                session,
                script_id=script.id,
                source=ErrorSourceEnum.local_script,
                diagnostic_message=diagnostic_message,
            )
        if status is not script.status:
            await script.update_values(session, status=status)
            await script.update_mtime(session)
        return status

    async def _write_script(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to write a script for processing

        Parameters
        ----------
        session : AnyAsyncSession
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
        session: AnyAsyncSession,
        script: Script,
        prod_area: str | Path,
    ) -> str:
        script_url = f"{prod_area}/{script.fullname}.sh"
        log_url = f"{prod_area}/{script.fullname}.log"
        stamp_url = f"{prod_area}/{script.fullname}.stamp"
        await script.update_values(session, script_url=script_url, log_url=log_url, stamp_url=stamp_url)
        return script_url

    async def _reset_script(
        self,
        session: AnyAsyncSession,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields: dict[str, Any] = {}
        update_fields["stamp_url"] = None
        if script.log_url:  # pragma: no cover
            await Path(script.log_url).unlink(missing_ok=True)
        if script.stamp_url:
            await Path(script.stamp_url).unlink(missing_ok=True)
        if to_status.value <= StatusEnum.ready.value:
            if script.script_url:
                await Path(script.script_url).unlink(missing_ok=True)
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
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method is ScriptMethodEnum.default:
            script_method = self.default_method
        if script_method is not ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_prepare(session, script, parent, **kwargs)
        if status is not script.status:
            await script.update_values(session, status=status)
            await script.update_mtime(session)
        return status

    async def launch(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method is ScriptMethodEnum.default:
            script_method = self.default_method

        if script_method is not ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_run(session, script, parent, **kwargs)
        if status is not script.status:
            await script.update_values(session, status=status)
            await script.update_mtime(session)
        return status

    async def check(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        script_method = script.method
        if script_method is ScriptMethodEnum.default:
            script_method = self.default_method

        if script_method is not ScriptMethodEnum.no_script:  # pragma: no cover
            raise CMBadExecutionMethodError(f"ScriptMethodEnum.no_script must be set for {type(self)}")
        status = await self._do_check(session, script, parent, **kwargs)
        await script.update_values(session, status=status)
        return status

    async def _do_prepare(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to prepare a `Script` for processing

        Parameters
        ----------
        session : AnyAsyncSession
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

    async def _do_run(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to process a `Script`

        Parameters
        ----------
        session : AnyAsyncSession
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

    async def _do_check(
        self,
        session: AnyAsyncSession,
        script: Script,
        parent: ElementMixin,
        **kwargs: Any,
    ) -> StatusEnum:
        """Hook for subclasses to check on `Script` processing

        Parameters
        ----------
        session : AnyAsyncSession
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
        session: AnyAsyncSession,
        script: Script,
        to_status: StatusEnum,
        *,
        fake_reset: bool = False,
    ) -> dict[str, Any]:
        update_fields = {}
        update_fields["status"] = to_status
        await self._purge_products(session, script, to_status, fake_reset=fake_reset)
        return update_fields
