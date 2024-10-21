from fastapi import APIRouter, Depends, HTTPException
from safir.dependencies.db_session import db_session_dependency
from sqlalchemy.ext.asyncio import async_scoped_session

from .. import db, models
from ..common import errors
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
    """Invoke the interface.get_element_by_fullname function"""
    try:
        async with session.begin():
            the_element = await interface.get_element_by_fullname(
                session,
                fullname,
            )
        return the_element
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/script",
    response_model=models.Script,
    summary="Get a script",
)
async def get_script(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Script:
    """Invoke the Script.get_row_by_fullname function"""
    try:
        async with session.begin():
            the_script = await db.Script.get_row_by_fullname(
                session,
                fullname,
            )
        return the_script
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/job",
    response_model=models.Job,
    summary="Get a job",
)
async def get_job(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Job:
    """Invoke the Job.get_row_by_fullname function"""
    try:
        async with session.begin():
            the_job = await db.Job.get_row_by_fullname(
                session,
                fullname,
            )
        return the_job
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/spec_block",
    response_model=models.SpecBlock,
    summary="Get a SpecBlock associated to an Object",
)
async def get_spec_block(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.SpecBlock:
    """Invoke the interface.get_spec_block function"""
    try:
        async with session.begin():
            the_spec_block = await interface.get_spec_block(
                session,
                fullname,
            )
        return the_spec_block
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/specification",
    response_model=models.Specification,
    summary="Get a Specficiation associated to an object",
)
async def get_specification(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> db.Specification:
    """Invoke the interface.get_specification function"""
    try:
        async with session.begin():
            the_specification = await interface.get_specification(
                session,
                fullname,
            )
        return the_specification
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/resolved_collections",
    response_model=dict,
    summary="Get resolved collections associated to an object",
)
async def get_resolved_collections(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_resolved_collections function"""
    try:
        async with session.begin():
            the_dict = await interface.get_resolved_collections(
                session,
                fullname,
            )
        return the_dict
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/collections",
    response_model=dict,
    summary="Get collections field associated to an object",
)
async def get_collections(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_collections function"""
    try:
        async with session.begin():
            the_dict = await interface.get_collections(
                session,
                fullname,
            )
        return the_dict
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/child_config",
    response_model=dict,
    summary="Get child_config field associated to an object",
)
async def get_child_config(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_child_config function"""
    try:
        async with session.begin():
            the_dict = await interface.get_child_config(
                session,
                fullname,
            )
        return the_dict
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/data_dict",
    response_model=dict,
    summary="Get data_dict field associated to an object",
)
async def get_data_dict(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_data_dict function"""
    try:
        async with session.begin():
            the_dict = await interface.get_data_dict(
                session,
                fullname,
            )
        return the_dict
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/spec_aliases",
    response_model=dict,
    summary="Get spec_aliases field associated to an object",
)
async def get_spec_aliases(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> dict:
    """Invoke the interface.get_spec_aliases function"""
    try:
        async with session.begin():
            the_dict = await interface.get_spec_aliases(
                session,
                fullname,
            )
        return the_dict
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/prerequisites",
    response_model=bool,
    summary="Check prerequisites associated to an object",
)
async def get_prerequisites(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> bool:
    """Invoke the interface.check_prerequisites function"""
    try:
        async with session.begin():
            ret_val = await interface.check_prerequisites(
                session,
                fullname=fullname,
            )
        return ret_val
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/element_scripts",
    response_model=list[models.Script],
    summary="Get the scripts associated to an Element",
)
async def get_element_scripts(
    fullname: str,
    script_name: str,
    *,
    remaining_only: bool = False,
    skip_superseded: bool = True,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.Script]:
    """Invoke the interface.get_scripts function"""
    try:
        async with session.begin():
            the_scripts = await interface.get_scripts(
                session,
                fullname=fullname,
                script_name=script_name,
                remaining_only=remaining_only,
                skip_superseded=skip_superseded,
            )
        return the_scripts
    except errors.CMMissingFullnameError as msg:
        raise HTTPException(status_code=404, detail=f"{str(msg)}") from msg
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/element_all_scripts",
    response_model=list[models.Script],
    summary="Get the scripts associated to an Element",
)
async def get_element_all_scripts(
    fullname: str,
    *,
    remaining_only: bool = False,
    skip_superseded: bool = True,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.Script]:
    """Invoke the interface.get_element_all_scripts function"""
    try:
        async with session.begin():
            the_scripts = await interface.get_all_scripts(
                session,
                fullname=fullname,
                remaining_only=remaining_only,
                skip_superseded=skip_superseded,
            )
        return the_scripts
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/element_jobs",
    response_model=list[models.Job],
    summary="Get the jobs associated to an Element",
)
async def get_element_jobs(
    fullname: str,
    *,
    remaining_only: bool = False,
    skip_superseded: bool = True,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.Job]:
    """Invoke the interface.get_jobs function"""
    try:
        async with session.begin():
            the_jobs = await interface.get_jobs(
                session,
                fullname=fullname,
                remaining_only=remaining_only,
                skip_superseded=skip_superseded,
            )
        return the_jobs
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/element_sleep_time",
    response_model=int,
    summary="Estimate the time to finish process an element",
)
async def get_element_sleep(
    fullname: str,
    job_sleep: int = 150,
    script_sleep: int = 15,
    session: async_scoped_session = Depends(db_session_dependency),
) -> int:
    """Invoke the interface.get_element_sleep function"""
    try:
        async with session.begin():
            return await interface.estimate_sleep(
                session,
                fullname=fullname,
                job_sleep=job_sleep,
                script_sleep=script_sleep,
            )
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/job/task_sets",
    response_model=list[models.TaskSet],
    summary="Get `TaskSet`s associated to a `Job`",
)
async def get_job_task_sets(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.TaskSet]:
    """Invoke the interface.get_job_task_sets function"""
    try:
        async with session.begin():
            return await interface.get_task_sets_for_job(
                session,
                fullname=fullname,
            )
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/job/wms_reports",
    response_model=list[models.WmsTaskReport],
    summary="Get `WmsTaskReport`s associated to a `Job`",
)
async def get_job_wms_reports(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.WmsTaskReport]:
    """Invoke the interface.get_wms_reports_for_job function"""
    try:
        async with session.begin():
            return await interface.get_wms_reports_for_job(
                session,
                fullname=fullname,
            )
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/job/product_sets",
    response_model=list[models.ProductSet],
    summary="Get `ProductSet`s associated to a `Job`",
)
async def get_job_product_sets(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.ProductSet]:
    """Invoke the interface.get_product_sets_for_job function"""
    try:
        async with session.begin():
            return await interface.get_product_sets_for_job(
                session,
                fullname=fullname,
            )
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg


@router.get(
    "/job/errors",
    response_model=list[models.PipetaskError],
    summary="Get `PipetaskErrors`s associated to a `Job`",
)
async def get_job_errors(
    fullname: str,
    session: async_scoped_session = Depends(db_session_dependency),
) -> list[db.PipetaskError]:
    """Invoke the interface.get_errors_for_job function"""
    try:
        async with session.begin():
            return await interface.get_errors_for_job(
                session,
                fullname=fullname,
            )
    except Exception as msg:
        raise HTTPException(status_code=500, detail=f"{str(msg)}") from msg
