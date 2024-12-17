from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Job
from lsst.cmservice.web_app.utils.utils import map_status


async def get_job_by_id(
    session: async_scoped_session,
    job_id: int,
) -> tuple[dict[str, Any] | None, list[dict[Any, Any]] | None]:
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

            aggregated_report_dict = {
                "running": 0,
                "succeeded": 0,
                "failed": 0,
                "pending": 0,
                "other": 0,
                "expected": 0,
            }

            if len(wms_report) > 0:
                aggregated_report_dict["succeeded"] = sum(task["n_succeeded"] for task in wms_report)
                aggregated_report_dict["failed"] = wms_report[-1]["n_failed"]
                aggregated_report_dict["running"] = wms_report[-1]["n_running"]
                aggregated_report_dict["pending"] = wms_report[-1]["n_pending"] + wms_report[-1]["n_ready"]
                aggregated_report_dict["other"] = (
                    wms_report[-1]["n_unknown"]
                    + wms_report[-1]["n_misfit"]
                    + wms_report[-1]["n_unready"]
                    + wms_report[-1]["n_deleted"]
                    + wms_report[-1]["n_pruned"]
                    + wms_report[-1]["n_held"]
                )

                aggregated_report_dict["expected"] = sum(aggregated_report_dict.values())

            products_dict = await job.get_products(session)
            products = [y.__dict__ for y in products_dict.reports.values()]

            collections = await job.resolve_collections(session, throw_overrides=False)
            scripts = await get_job_scripts(session, job)
            job_details = {
                "id": job.id,
                "name": job.name,
                "fullname": job.fullname,
                "superseded": job.superseded,
                "status": map_status(job.status),
                "data": job.data,
                "collections": {key: collections[key] for key in collections if key.startswith("job_")},
                "child_config": job.child_config,
                "wms_report": wms_report,
                "aggregated_wms_report": aggregated_report_dict,
                "products": products,
            }

        return job_details, scripts


async def get_job_scripts(session: async_scoped_session, job: Job) -> list[dict]:
    scripts = await job.get_scripts(session)
    job_scripts = []
    for script in scripts:
        job_scripts.append(
            {
                "id": script.id,
                "name": script.name,
                "fullname": script.fullname,
                "superseded": script.superseded,
                "status": str(script.status.name).upper(),
                "log_url": script.log_url,
            },
        )
    return job_scripts
