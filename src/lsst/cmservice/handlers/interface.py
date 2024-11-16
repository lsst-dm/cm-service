# pylint: disable=too-many-lines
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db
from ..common.enums import LevelEnum, NodeTypeEnum, StatusEnum, TableEnum
from ..common.errors import (
    CMBadEnumError,
    CMBadExecutionMethodError,
    CMBadFullnameError,
    CMIntegrityError,
    CMMissingFullnameError,
    test_type_and_raise,
)
from . import functions

TABLE_DICT: dict[TableEnum, type[db.RowMixin]] = {
    TableEnum.production: db.Production,
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
    TableEnum.script_template: db.ScriptTemplate,
}


LEVEL_DICT: dict[LevelEnum, type[db.NodeMixin]] = {
    LevelEnum.campaign: db.Campaign,
    LevelEnum.step: db.Step,
    LevelEnum.group: db.Group,
    LevelEnum.job: db.Job,
    LevelEnum.script: db.Script,
}


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
    session: async_scoped_session,
    row_id: int,
    table_enum: TableEnum,
) -> db.RowMixin:
    """Get a row from a table

    Parameters
    ----------
    session : async_scoped_session
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
        raise CMBadEnumError(f"Unknown table {table_enum}") from e
    query = select(table_class).where(table_class.id == row_id)
    result_s = await session.scalars(query)
    result = None if result_s is None else result_s.first()
    if result is None:
        raise CMMissingFullnameError(f"{table_class} {row_id} not found")
    return result


async def get_node_by_level_and_id(
    session: async_scoped_session,
    element_id: int,
    level: LevelEnum,
) -> db.NodeMixin:
    """Get a `Node` from the DB

    Parameters
    ----------
    session : async_scoped_session
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
        raise CMBadEnumError(f"Unknown level {level}") from e
    result = await session.get(element_class, element_id)
    if result is None:
        raise CMMissingFullnameError(f"{element_class} {element_id} not found")
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
    session: async_scoped_session,
    fullname: str,
) -> db.ElementMixin:
    """Get a `Element` from the DB

    Parameters
    ----------
    session : async_scoped_session
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
    element: db.ElementMixin | db.Production | None = None
    if n_slash == 0:
        raise CMBadFullnameError(f"Can not figure out Table for fullname {fullname}, not enough fields")
    if n_slash == 1:
        element = await db.Campaign.get_row_by_fullname(session, fullname)
    elif n_slash == 2:
        element = await db.Step.get_row_by_fullname(session, fullname)
    elif n_slash == 3:
        element = await db.Group.get_row_by_fullname(session, fullname)
    elif n_slash == 4:
        element = await db.Job.get_row_by_fullname(session, fullname)
    else:
        raise CMBadFullnameError(f"Can not figure out Table for fullname {fullname}, too many fields")
    return element


async def get_node_by_fullname(
    session: async_scoped_session,
    fullname: str,
) -> db.NodeMixin:
    """Get a `Node` from the DB

    Parameters
    ----------
    session : async_scoped_session
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
    if node_type == NodeTypeEnum.element:
        return await get_element_by_fullname(session, fullname)
    result = await db.Script.get_row_by_fullname(session, fullname[7:])
    return result


async def process_script(
    session: async_scoped_session,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process a Script

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process an `Element`

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    fullname: str,
    fake_status: StatusEnum | None = None,
) -> tuple[bool, StatusEnum]:
    """Process a `Node`

    Parameters
    ----------
    session : async_scoped_session
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
    if node_type == NodeTypeEnum.element:
        return await process_element(session, fullname, fake_status=fake_status)
    if node_type == NodeTypeEnum.script:
        return await process_script(session, fullname[7:], fake_status=fake_status)
    raise CMBadExecutionMethodError(
        f"Tried to process an row from a table of type {node_type}"
    )  # pragma: no cover


async def reset_script(
    session: async_scoped_session,
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
    session : async_scoped_session
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
    session: async_scoped_session,
    fullname: str,
) -> db.Job:
    """Run a rescue on a `Job`

    Notes
    -----
    This can only be run on rescuable Job

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    fullname: str,
) -> list[db.Job]:
    """Mark a `Job` as rescued

    Notes
    -----
    This can only be run on rescuable jobs

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    **kwargs: Any,
) -> db.Campaign:
    """Create a new Campaign

    Parameters
    ----------
    session : async_scoped_session
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


async def load_specification(
    session: async_scoped_session,
    yaml_file: str,
    *,
    allow_update: bool = False,
) -> db.Specification:
    """Load a Specification from a yaml file

    Parameters
    ----------
    session : async_scoped_session
        DB session manager

    yaml_file: str,
        Path to the yaml file

    allow_update: bool
        Allow updating existing items

    Returns
    -------
    specification : `Specification`
        Newly created `Specification`
    """
    result = await functions.load_specification(session, yaml_file, {}, allow_update=allow_update)
    if result is None:  # pragma: no cover
        raise ValueError("load_specification() did not return a Specification")
    return result


async def load_and_create_campaign(  # pylint: disable=too-many-arguments
    session: async_scoped_session,
    yaml_file: str,
    parent_name: str,
    name: str,
    spec_block_assoc_name: str | None = None,
    **kwargs: Any,
) -> db.Campaign:
    """Load a Specification and use it to create a `Campaign`

    Parameters
    ----------
    session : async_scoped_session
        DB session manager

    yaml_file: str
        Path to the yaml file

    parent_name: str
        Name for the `Production` and default value for spec_name

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
    specification = await load_specification(session, yaml_file, allow_update=allow_update)

    try:
        await db.Production.create_row(session, name=parent_name)
    except CMIntegrityError:  # pragma: no cover
        pass

    if not spec_block_assoc_name:  # pragma: no cover
        spec_block_assoc_name = f"{specification.name}#campaign"

    kwargs.update(
        spec_block_assoc_name=spec_block_assoc_name,
        parent_name=parent_name,
        name=name,
    )

    result = await create_campaign(
        session,
        **kwargs,
    )
    # await session.commit()
    return result


async def add_steps(
    session: async_scoped_session,
    fullname: str,
    child_configs: list[dict[str, Any]],
) -> db.Campaign:
    """Add Steps to a `Campaign`

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    yaml_file: str,
) -> list[db.PipetaskErrorType]:
    """Load a set of `PipetaskErrorType`s from a yaml file

    Parameters
    ----------
    session : async_scoped_session
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
    session: async_scoped_session,
    yaml_file: str,
    fullname: str,
    *,
    allow_update: bool = False,
) -> db.Job:
    """Load a manifest checker yaml file

    Parameters
    ----------
    session : async_scoped_session
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


async def match_pipetask_errors(  # pylint: disable=unused-argument
    session: async_scoped_session,
    *,
    rematch: bool = False,
) -> list[db.PipetaskError]:
    """Match PipetaskErrors to PipetaskErrorTypes

    FIXME: implement this function

    Parameters
    ----------
    session : async_scoped_session
        DB session manager

    rematch: bool
        Rematch already matched PipetaskErrors

    Returns
    -------
    error_instances : List[PipetaskError]
        Newly matched (or rematched) PipetaskErrors
    """
    return []
