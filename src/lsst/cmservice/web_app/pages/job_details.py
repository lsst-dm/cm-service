from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Job
from lsst.cmservice.web_app.utils.utils import map_status


async def get_job_by_id(
    session: async_scoped_session,
    job_id: int,
) -> tuple[dict[str, Any] | None, list[dict[Any, Any]] | None, list[dict[Any, Any]] | None]:
    q = select(Job).where(Job.id == job_id)
    async with session.begin_nested():
        results = await session.scalars(q)
        job = results.first()

        job_details = None
        scripts = None
        products = None

        if job is not None:
            wms_reports_dict = await job.get_wms_reports(session)
            wms_report = [y.__dict__ for y in wms_reports_dict.reports.values()]

            collections = await job.resolve_collections(session)
            scripts = await get_job_scripts(session, job)
            job_details = {
                "id": job.id,
                "name": job.name,
                "fullname": job.fullname,
                "superseded": job.superseded,
                "status": map_status(job.status),
                "data": job.data,
                "collections": collections,
                "child_config": job.child_config,
                "wms_report": wms_report,
            }

            products_dict = await job.get_products(session)
            products = [y.__dict__ for y in products_dict.reports.values()]
            print(products)

        return job_details, scripts, products


async def get_job_scripts(session: async_scoped_session, job: Job) -> list[dict]:
    scripts = await job.get_scripts(session)
    job_scripts = []
    for script in scripts:
        job_scripts.append(
            {
                "id": script.id,
                "name": script.name,
                "superseded": script.superseded,
                "status": map_status(script.status),
            },
        )
    return job_scripts
