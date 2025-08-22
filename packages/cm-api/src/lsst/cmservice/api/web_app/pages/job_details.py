from typing import Any

from sqlalchemy import select

from lsst.cmservice.api.web_app.utils.utils import map_status
from lsst.cmservice.core.common.types import AnyAsyncSession
from lsst.cmservice.core.db import Job, NodeMixin


async def get_job_by_id(
    session: AnyAsyncSession,
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
                aggregated_report_dict["failed"] = sum(task["n_failed"] for task in wms_report)
                aggregated_report_dict["running"] = sum(task["n_running"] for task in wms_report)
                aggregated_report_dict["pending"] = sum(
                    task["n_pending"] + task["n_ready"] for task in wms_report
                )
                aggregated_report_dict["other"] = sum(
                    (
                        task["n_unknown"]
                        + task["n_misfit"]
                        + task["n_unready"]
                        + task["n_deleted"]
                        + task["n_pruned"]
                        + task["n_held"]
                    )
                    for task in wms_report
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
                "org_status": {"name": job.status.name, "value": job.status.value},
                "data": job.data,
                "collections": {key: collections[key] for key in collections if key.startswith("job_")},
                "child_config": job.child_config,
                "wms_report": wms_report,
                "aggregated_wms_report": aggregated_report_dict,
                "products": products,
                "level": job.level.value,
            }

        return job_details, scripts


async def get_job_scripts(session: AnyAsyncSession, job: Job) -> list[dict]:
    scripts = await job.get_scripts(session)
    job_scripts = [
        {
            "id": script.id,
            "name": script.name,
            "fullname": script.fullname,
            "superseded": script.superseded,
            "status": str(script.status.name).upper(),
            "log_url": script.log_url,
        }
        for script in scripts
    ]
    return job_scripts


async def get_job_node(session: AnyAsyncSession, job_id: int) -> NodeMixin:
    job = await Job.get_row(session, job_id)
    return job
