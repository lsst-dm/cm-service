from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_scoped_session

from lsst.cmservice.db import Group
from lsst.cmservice.web_app.utils.utils import map_status


async def get_group_by_id(
    session: async_scoped_session,
    group_id: int,
):
    q = select(Group).where(Group.id == group_id)
    async with session.begin_nested():
        results = await session.scalars(q)
        group = results.first()
        wms_reports_dict = await group.get_wms_reports(session)
        wms_report = [y.__dict__ for y in wms_reports_dict.reports.values()]

        aggregated_report_dict = {"running": 0, "succeeded": 0, "failed": 0, "pending": 0, "other": 0}
        for task in wms_report:
            aggregated_report_dict["succeeded"] += task["n_succeeded"]
            aggregated_report_dict["failed"] += task["n_failed"]
            aggregated_report_dict["running"] += task["n_running"]
            aggregated_report_dict["pending"] += task["n_pending"] + task["n_ready"]
            aggregated_report_dict["other"] += (
                task["n_unknown"]
                + task["n_misfit"]
                + task["n_unready"]
                + task["n_deleted"]
                + task["n_pruned"]
                + task["n_held"]
            )

        aggregated_report_dict["expected"] = sum(aggregated_report_dict.values())
        print(aggregated_report_dict)

        collections = await group.resolve_collections(session)
        jobs = await get_group_jobs(session, group)
        scripts = await get_group_scripts(session, group)
        group_details = {
            "id": group.id,
            "name": group.name,
            "fullname": group.fullname,
            "superseded": group.superseded,
            "status": map_status(group.status),
            "data": group.data,
            "collections": collections,
            "child_config": group.child_config,
            "wms_report": wms_report,
            "aggregated_wms_report": aggregated_report_dict,
        }

        return group_details, jobs, scripts


async def get_group_jobs(session: async_scoped_session, group: Group) -> list[dict]:
    jobs = await group.children(session)
    group_jobs = []
    for job in jobs:
        group_jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "superseded": job.superseded,
                "status": map_status(job.status),
                "data": job.data,
                "submit_status": "Submitted" if job.wms_job_id is not None else "",
                "submit_url": job.wms_job_id if not job.wms_job_id.isnumeric() else "",
                "stamp_url": job.stamp_url,
            },
        )
    return group_jobs


async def get_group_scripts(session: async_scoped_session, group: Group) -> list[dict]:
    scripts = await group.get_scripts(session)
    step_scripts = []
    for script in scripts:
        step_scripts.append(
            {
                "id": script.id,
                "name": script.name,
                "superseded": script.superseded,
                "status": map_status(script.status),
            },
        )
    return step_scripts
