from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlmodel import col
from sqlmodel import select as select_

from .. import db
from ..common.enums import LevelEnum, NodeTypeEnum, StatusEnum, TableEnum
from ..common.errors import (
    CMBadEnumError,
    CMBadExecutionMethodError,
    CMBadFullnameError,
    CMMissingFullnameError,
    test_type_and_raise,
)
from ..common.logging import LOGGER
from ..common.types import AnyAsyncSession, AsyncSession
from ..db.campaigns_v2 import ActivityLog
from . import functions

TABLE_DICT: dict[TableEnum, type[db.RowMixin]] = {
    TableEnum.campaign: db.Campaign,
    TableEnum.step: db.Step,
    TableEnum.group: db.Group,
    TableEnum.script: db.Script,
    TableEnum.job: db.Job,
    TableEnum.step_dependency: db.StepDependency,
    TableEnum.script_dependency: db.ScriptDependency,
    TableEnum.pipetask_error_type: db.PipetaskErrorType,
    TableEnum.pipetask_error: db.PipetaskError,
    TableEnum.script_error: db.ScriptError,
    TableEnum.task_set: db.TaskSet,
    TableEnum.product_set: db.ProductSet,
    TableEnum.specification: db.Specification,
    TableEnum.spec_block: db.SpecBlock,
}


LEVEL_DICT: dict[LevelEnum, type[db.NodeMixin]] = {
    LevelEnum.campaign: db.Campaign,
    LevelEnum.step: db.Step,
    LevelEnum.group: db.Group,
    LevelEnum.job: db.Job,
    LevelEnum.script: db.Script,
}


logger = LOGGER.bind(module=__name__)


def get_table(
    table_enum: TableEnum,
) -> type[db.RowMixin]:
    """Get any table

    Parameters
    ----------
    table_enum : TableEnum
        Which table do we want

    Returns
    -------
    table_class : type[db.RowMixin]
        The class that defines the table
    """
    return TABLE_DICT[table_enum]


async def get_row_by_table_and_id(
    session: AnyAsyncSession,
    row_id: int,
    table_enum: TableEnum,
) -> db.RowMixin:
    """Get a row from a table

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    row_id: int
        Primary Key for the row we want

    table_enum : TableEnum
        Which table do we want

    Returns
    -------
    row : db.RowMixin
        Requested row

    Raises
    ------
    CMBadEnumError : Table enum does not match a known table

    CMMissingFullnameError : No such row was found
    """
    try:
        table_class = get_table(table_enum)
    except KeyError as e:
        msg = f"Unknown table {table_enum}"
        raise CMBadEnumError(msg) from e
    query = select(table_class).where(table_class.id == row_id)
    result_s = await session.scalars(query)
    result = None if result_s is None else result_s.first()
    if result is None:
        msg = f"{table_class} {row_id} not found"
        raise CMMissingFullnameError(msg)
    return result


async def get_node_by_level_and_id(
    session: AnyAsyncSession,
    element_id: int,
    level: LevelEnum,
) -> db.NodeMixin:
    """Get a `Node` from the DB

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    element_id: int
        Primary Key for the `Element` we want

    level : LevelEnum
        Which table do we want

    Returns
    -------
    result : db.NodeMixin
        Requested node item

    Raises
    ------
    CMBadEnumError : level enum does not match a known table

    CMMissingFullnameError : No such element was found
    """
    try:
        element_class = LEVEL_DICT[level]
    except KeyError as e:
        msg = f"Unknown level {level}"
        raise CMBadEnumError(msg) from e
    result = await session.get(element_class, element_id)
    if result is None:
        msg = f"{element_class} {element_id} not found"
        raise CMMissingFullnameError(msg)
    return result


def get_node_type_by_fullname(
    fullname: str,
) -> NodeTypeEnum:
    """Get the type of Node from a fullname

    Parameters
    ----------
    fullname: str
        Full unique name for the `Node`

    Returns
    -------
    node_type: NodeTypeEnum
        The node type
    """
    if fullname.find("script:") == 0:
        return NodeTypeEnum.script
    return NodeTypeEnum.element


async def get_element_by_fullname(
    session: AnyAsyncSession,
    fullname: str,
) -> db.ElementMixin:
    """Get a `Element` from the DB

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the `Element`

    Returns
    -------
    element : db.ElementMixin
        Requested element

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMMissingFullnameError : No such element was found
    """
    n_slash = fullname.count("/")
    element: db.ElementMixin | None = None
    if n_slash > 3 or not len(fullname):
        message = f"Can not figure out Table for bad fullname {fullname}"
        logger.error(message)
        raise CMBadFullnameError(message)
    elif n_slash == 0:
        element = await db.Campaign.get_row_by_fullname(session, fullname)
    elif n_slash == 1:
        element = await db.Step.get_row_by_fullname(session, fullname)
    elif n_slash == 2:
        element = await db.Group.get_row_by_fullname(session, fullname)
    elif n_slash == 3:
        element = await db.Job.get_row_by_fullname(session, fullname)
    if TYPE_CHECKING:
        assert element is not None
    return element


async def get_node_by_fullname(
    session: AnyAsyncSession,
    fullname: str,
) -> db.NodeMixin:
    """Get a `Node` from the DB

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the `Node`


    Returns
    -------
    result : db.NodeMixin
        Requested node

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMMissingFullnameError : No such element was found
    """
    node_type = get_node_type_by_fullname(fullname)
    if node_type is NodeTypeEnum.element:
        return await get_element_by_fullname(session, fullname)
    result = await db.Script.get_row_by_fullname(session, fullname[7:])
    return result


async def process_script(
    session: AnyAsyncSession,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process a Script

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the `Script`

    fake_status: StatusEnum | None
        If not none, will set the status of running scripts to this value

    Returns
    -------
    changed : bool
        True if anything changed
    status : StatusEnum
        Processing status

    Raises
    ------
    CMMissingFullnameError : Could not find Script
    """
    script = await db.Script.get_row_by_fullname(session, fullname)
    changed, result = await script.process(session, fake_status=fake_status)
    await session.commit()
    return changed, result


async def process_element(
    session: AnyAsyncSession,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process an `Element`

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the `Element`

    fake_status: StatusEnum | None
        If not none, will set the status of running scripts to this value

    Returns
    -------
    changed : bool
        True if anything changed
    status : StatusEnum
        Processing status

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMMissingFullnameError : Could not find Job
    """
    element = await get_element_by_fullname(session, fullname)
    changed, result = await element.process(session, fake_status=fake_status)
    await session.commit()
    return changed, result


async def process(
    session: AnyAsyncSession,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process a `Node`

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the `Element`

    fake_status: StatusEnum | None
        If not none, will set the status of running scripts to this value

    Returns
    -------
    changed : bool
        True if anything changed
    status : StatusEnum
        Processing status

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMMissingFullnameError : Could not find Node

    CMBadExecutionMethodError: Called on the wrong type of table
    """
    node_type = get_node_type_by_fullname(fullname)
    if node_type is NodeTypeEnum.element:
        return await process_element(session, fullname, fake_status=fake_status)
    elif node_type is NodeTypeEnum.script:
        return await process_script(session, fullname[7:], fake_status=fake_status)
    else:
        msg = f"Tried to process an row from a table of type {node_type}"
        raise CMBadExecutionMethodError(msg)  # pragma: no cover


async def reset_script(
    session: AnyAsyncSession,
    fullname: str,
    status: StatusEnum,
    *,
    fake_reset: bool = False,
) -> db.Script:
    """Run a retry on a `Script`

    Notes
    -----
    This can only be run on failed/rejected scripts

    This will mark the current version of the
    script as superseded and create a new version
    of the Script

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the script

    status: StatusEnum
        Status to set script to

    fake_reset: bool
        Don't actually try to remove collections if True

    Returns
    -------
    script : Script
        Script in question

    Raises
    ------
    CMBadStateTransitionError : Script was not in failed/rejected status

    CMMissingFullnameError : Could not find Node
    """
    script = await db.Script.get_row_by_fullname(session, fullname)
    _result = await script.reset_script(session, status, fake_reset=fake_reset)
    return script


async def rescue_job(
    session: AnyAsyncSession,
    fullname: str,
) -> db.Job:
    """Run a rescue on a `Job`

    Notes
    -----
    This can only be run on rescuable Job

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the parent `Element`

    Returns
    -------
    job : Job
        Newly created Job

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMBadStateTransitionError : Active script was not in rescuable status

    ValueError : No rescuable scripts found

    CMMissingFullnameError : Could not find Element
    """
    element = await get_element_by_fullname(session, fullname)
    element = test_type_and_raise(element, db.Group, "rescue_job element")
    return await element.rescue_job(session)


async def mark_job_rescued(
    session: AnyAsyncSession,
    fullname: str,
) -> list[db.Job]:
    """Mark a `Job` as rescued

    Notes
    -----
    This can only be run on rescuable jobs

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the parent `Element`

    Returns
    -------
    job : Job
        Processing status

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMBadStateTransitionError : Active job was not in rescuable status

    ValueError : More that one active and accepted job found

    ValueError : No rescuable jobs found

    CMMissingFullnameError : Could not find Element
    """
    element = await get_element_by_fullname(session, fullname)
    element = test_type_and_raise(element, db.Group, "mark_job_rescued element")
    return await element.mark_job_rescued(session)


async def create_campaign(
    session: AnyAsyncSession,
    **kwargs: Any,
) -> db.Campaign:
    """Create a new Campaign

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    kwargs : Any
        Passed to Campaign construction

    Returns
    -------
    campaign: Campaign
        Newly created Campaign
    """
    result = await db.Campaign.create_row(session, **kwargs)
    return result


async def load_and_create_campaign(
    session: AnyAsyncSession,
    yaml_file: str,
    name: str,
    spec_block_assoc_name: str | None = None,
    **kwargs: Any,
) -> db.Campaign:
    """Load a Specification and use it to create a `Campaign`

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    yaml_file: str
        Path to the yaml file

    name: str,
        Name for the `Campaign` and default value for spec_block_name

    spec_block_assoc_name: str | None=None,
        Combined name of Specification and SpecBlock

    Returns
    -------
    campaign : `Campaign`
        Newly created `Campaign`
    """
    allow_update = kwargs.get("allow_update", False)
    specification = await functions.load_specification(session, yaml_file, allow_update=allow_update)

    if not spec_block_assoc_name:  # pragma: no cover
        spec_block_assoc_name = f"{specification.name}#campaign"

    kwargs.update(
        spec_block_assoc_name=spec_block_assoc_name,
        name=name,
    )

    campaign = await create_campaign(
        session,
        **kwargs,
    )

    await functions.render_campaign_steps(campaign=campaign, session=session)
    return campaign


async def add_steps(
    session: AnyAsyncSession,
    fullname: str,
    child_configs: list[dict[str, Any]],
) -> db.Campaign:
    """Add Steps to a `Campaign`

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    fullname: str
        Full unique name for the parent `Campaign`

    child_configs: list[dict[str, Any]]
        Configurations for the `Step`s to be created

    Returns
    -------
    campaign : Campaign
        Newly updated Campaign

    Raises
    ------
    CMBadFullnameError : could not parse fullname to determine table

    CMMissingFullnameError : Could not find Element
    """
    campaign = await db.Campaign.get_row_by_fullname(session, fullname)
    result = await functions.add_steps(session, campaign, child_configs)
    return result


async def load_error_types(
    session: AnyAsyncSession,
    yaml_file: str,
) -> list[db.PipetaskErrorType]:
    """Load a set of `PipetaskErrorType`s from a yaml file

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    yaml_file: str,
        Path to the yaml file

    Returns
    -------
    error_types : List[PipetaskErrorType]
        New created PipetaskErrorTypes
    """
    error_types = await functions.load_error_types(session, yaml_file)
    return error_types


async def load_manifest_report(
    session: AnyAsyncSession,
    yaml_file: str,
    fullname: str,
    *,
    allow_update: bool = False,
) -> db.Job:
    """Load a manifest checker yaml file

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    yaml_file: str,
        Path to the yaml file

    fullname: str
        Fullname of the `Job` to associate with this report

    allow_update: bool
        If set, allow updating values

    Returns
    -------
    job: Job
        Newly updated job
    """
    result = await functions.load_manifest_report(session, fullname, yaml_file, allow_update=allow_update)
    return result


async def match_pipetask_errors(
    session: AnyAsyncSession,
    *,
    rematch: bool = False,
) -> list[db.PipetaskError]:
    """Match PipetaskErrors to PipetaskErrorTypes

    FIXME: implement this function

    Parameters
    ----------
    session : AnyAsyncSession
        DB session manager

    rematch: bool
        Rematch already matched PipetaskErrors

    Returns
    -------
    error_instances : List[PipetaskError]
        Newly matched (or rematched) PipetaskErrors
    """
    return []


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
        select_(ActivityLog)
        .where(col(ActivityLog.namespace) == campaign)
        .where(col(ActivityLog.detail)["error"].is_not(None))
    )
    error_log_entries = (await session.exec(s)).all()
    return error_log_entries
