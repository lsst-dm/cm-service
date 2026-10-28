import re
from collections.abc import Sequence
from uuid import UUID

from anyio import Path
from sqlmodel import col, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from lsst.cmservice.models.db.campaigns import ActivityLog, Manifest
from lsst.cmservice.models.enums import StatusEnum
from lsst.cmservice.models.types import KindField
from lsst.ctrl.bps.wms_service import WmsRunReport, WmsStates

from ..common.logging import LOGGER
from ..config import config

logger = LOGGER.bind(module=__name__)


async def set_manifest_default_for_campaign(
    session: AsyncSession,
    *,
    manifest: Manifest | None = None,
    campaign_id: UUID | None = None,
    manifest_id: UUID | None = None,
    kind: KindField | None = None,
) -> None:
    """Set the manifest as the default for the given namespace."""
    if manifest is not None:
        campaign_id = manifest.namespace
        manifest_id = manifest.id
        kind = manifest.kind

    await session.exec(
        update(Manifest)
        .where(
            col(Manifest.namespace) == campaign_id,
            col(Manifest.kind) == kind,
            col(Manifest.default).is_(True),
        )
        .values(default=False)
    )
    await session.exec(update(Manifest).where(col(Manifest.id) == manifest_id).values(default=True))


async def get_activity_log_errors(
    session: AsyncSession,
    campaign: str | UUID,
) -> Sequence[ActivityLog]:
    """Queries the activity log table and returns entries that represent error
    conditions, i.e., the `detail` JSONB column has an "error" key.

    Parameters
    ----------
    session : AsyncSession
        A sqlmodel Async Session

    campaign: UUID | str
        A campaign id as a UUID or a str that can be cast as a UUID.

    Returns
    -------
    error_instances : Sequence[ActivityLog]
        A list of Campaign activity log entries that contain errors.
    """
    s = (
        select(ActivityLog)
        .where(col(ActivityLog.namespace) == campaign)
        .where(col(ActivityLog.detail)["error"].is_not(None))
    )
    error_log_entries = (await session.exec(s)).all()
    return error_log_entries


def status_from_bps_report(
    wms_run_report: WmsRunReport | None,
    fake_status: StatusEnum | None = None,
) -> StatusEnum:
    """Decide the status for a workflow for a bps report

    Parameters
    ----------
    wms_run_report: WmsRunReport,
        bps report return object

    Returns
    -------
    status: StatusEnum
        The status to set for the bps_report script
    """
    # FIXME: this function must communicate more explicitly the conditions it
    # discovers. The APIs for obtaining wms status are lacking in filtering
    # capabilities and the CLI doesn't have good tools for showing the status
    # of a task.
    if wms_run_report is None:
        return fake_status or config.mock_status or StatusEnum.accepted

    the_state = wms_run_report.state
    logger.debug("Deriving status from BPS report", status=the_state)

    # If any of the jobs are in a HELD state, this requires intervention
    # and a notification should be sent and A BLOCKED status returned
    for blocked_job in filter(lambda x: x.state is WmsStates.HELD, wms_run_report.jobs):
        return StatusEnum.blocked

    # If pipetaskInit has failed, return failed
    for pipetask_init in filter(lambda x: x.name == "pipetaskInit", wms_run_report.jobs):
        if pipetask_init.state == WmsStates.FAILED:
            return StatusEnum.failed
        # There should only ever be one pipetaskInit but to prevent weird loops
        break

    if the_state == WmsStates.RUNNING:
        return StatusEnum.running
    elif the_state == WmsStates.SUCCEEDED:
        return StatusEnum.accepted
    elif the_state == WmsStates.DELETED:
        # TODO the DELETED state could reasonably be considered "rejected"
        # since it is probably the result of manual cancellation.
        return StatusEnum.failed
    elif the_state in [
        WmsStates.UNKNOWN,
        WmsStates.MISFIT,
        WmsStates.PRUNED,
        WmsStates.UNREADY,
        WmsStates.READY,
        WmsStates.HELD,
        WmsStates.PENDING,
    ]:
        return StatusEnum.failed

    for final_job in filter(lambda x: x.name == "finalJob", wms_run_report.jobs):
        if final_job.state == WmsStates.SUCCEEDED:
            # we want downstream scripts, e..g, pipetask report, to run
            return StatusEnum.accepted
        # There should only ever be one finalJob but to prevent weird loops
        break

    # In any cases not previously handled, return a reviewable status
    return StatusEnum.reviewable


async def parse_bps_stdout(url: str | Path) -> dict[str, str]:
    """Parse the stdout from a bps submit job.

    Parameters
    ----------
    url : `str | anyio.Path`
        url for BPS submit stdout

    Returns
    -------
    out_dict `str`
        a dictionary containing the stdout from BPS submit
    """
    bps_stdout_parser = re.compile(r"^(?P<token>[\w \t]+):\s*(?P<value>.*)$", re.MULTILINE)
    out_dict = {}
    stdout = await Path(url).read_text()
    for match in re.finditer(bps_stdout_parser, stdout):
        out_dict[match.group("token")] = match.group("value")
    return out_dict
