from typing import List

from fastapi import APIRouter, Depends
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..handlers import interface

router = APIRouter(
    prefix="/get",
    tags=["Query"],
)


@router.get(
    "/element",
    response_model=models.Element,
    summary="Get an element, i.e., a Campaign, Step or Group",
)
async def get_element(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.ElementMixin:
    result = await interface.get_element_by_fullname(
        session,
        fullname,
    )
    return result


@router.get(
    "/script",
    response_model=models.Script,
    summary="Get a script",
)
async def get_script(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Script:
    result = await db.Script.get_row_by_fullname(
        session,
        fullname,
    )
    return result


@router.get(
    "/job",
    response_model=models.Job,
    summary="Get a job",
)
async def get_job(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Job:
    result = await db.Job.get_row_by_fullname(
        session,
        fullname,
    )
    return result


@router.get(
    "/spec_block",
    response_model=models.SpecBlock,
    summary="Get a SpecBlock associated to an Object",
)
async def get_spec_block(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.SpecBlock:
    result = await interface.get_spec_block(
        session,
        fullname,
    )
    return result


@router.get(
    "/specification",
    response_model=models.Specification,
    summary="Get a Specficiation associated to an object",
)
async def get_specification(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Specification:
    result = await interface.get_specification(
        session,
        fullname,
    )
    return result


@router.get(
    "/resolved_collections",
    response_model=dict,
    summary="Get resolved collections associated to an object",
)
async def get_resolved_collections(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    result = await interface.get_resolved_collections(
        session,
        fullname,
    )
    return result


@router.get(
    "/collections",
    response_model=dict,
    summary="Get collections field associated to an object",
)
async def get_collections(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    result = await interface.get_collections(
        session,
        fullname,
    )
    return result


@router.get(
    "/child_config",
    response_model=dict,
    summary="Get child_config field associated to an object",
)
async def get_child_config(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    result = await interface.get_child_config(
        session,
        fullname,
    )
    return result


@router.get(
    "/data_dict",
    response_model=dict,
    summary="Get data_dict field associated to an object",
)
async def get_data_dict(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    result = await interface.get_data_dict(
        session,
        fullname,
    )
    return result


@router.get(
    "/spec_aliases",
    response_model=dict,
    summary="Get spec_aliases field associated to an object",
)
async def get_spec_aliases(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    result = await interface.get_spec_aliases(
        session,
        fullname,
    )
    return result


@router.get(
    "/prerequisites",
    response_model=bool,
    summary="Check prerequisites associated to an object",
)
async def get_prerequisites(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> bool:
    result = await interface.check_prerequisites(
        session,
        fullname=fullname,
    )
    return result


@router.get(
    "/scripts",
    response_model=list[models.Script],
    summary="Get the scripts associated to an Element",
)
async def get_scripts(
    fullname: str,
    script_name: str,
    remaining_only: bool = False,
    skip_superseded: bool = True,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.Script]:
    result = await interface.get_scripts(
        session,
        fullname=fullname,
        script_name=script_name,
        remaining_only=remaining_only,
        skip_superseded=skip_superseded,
    )
    return result


@router.get(
    "/jobs",
    response_model=list[models.Job],
    summary="Get the jobs associated to an Element",
)
async def get_jobs(
    fullname: str,
    remaining_only: bool = False,
    skip_superseded: bool = True,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.Job]:
    result = await interface.get_jobs(
        session,
        fullname=fullname,
        remaining_only=remaining_only,
        skip_superseded=skip_superseded,
    )
    return result


@router.get(
    "/job/task_sets",
    response_model=list[models.TaskSet],
    summary="Get `TaskSet`s associated to a `Job`",
)
async def get_job_task_sets(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.TaskSet]:
    result = await interface.get_task_sets_for_job(
        session,
        fullname=fullname,
    )
    return result


@router.get(
    "/job/wms_reports",
    response_model=list[models.WmsTaskReport],
    summary="Get `WmsTaskReport`s associated to a `Job`",
)
async def get_job_wms_reports(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.WmsTaskReport]:
    result = await interface.get_wms_reports_for_job(
        session,
        fullname=fullname,
    )
    return result


@router.get(
    "/job/product_sets",
    response_model=list[models.ProductSet],
    summary="Get `ProductSet`s associated to a `Job`",
)
async def get_job_product_sets(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.ProductSet]:
    result = await interface.get_product_sets_for_job(
        session,
        fullname=fullname,
    )
    return result


@router.get(
    "/job/errors",
    response_model=list[models.PipetaskError],
    summary="Get `PipetaskErrors`s associated to a `Job`",
)
async def get_job_errors(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> List[db.PipetaskError]:
    result = await interface.get_errors_for_job(
        session,
        fullname=fullname,
    )
    return result
