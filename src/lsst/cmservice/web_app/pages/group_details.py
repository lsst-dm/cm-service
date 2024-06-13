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
        print(f"group id: {group.id}")
        reports = await group.get_wms_reports(session)
        wms_report = []
        for report in reports:
            tasks = report[1]
            for task in tasks:
                print(f"TASK {task}: {tasks[task].n_succeeded}")
                wms_report.append(f"{task} - succeeded: {tasks[task].n_succeeded}")
            # print(reports[report].n_succeeded)
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
        }

        return group_details, jobs, scripts


async def get_group_jobs(session: async_scoped_session, group: Group) -> list[dict]:
    jobs = await group.children(session)
    group_jobs = []
    for job in jobs:
        # print(f"job id: {job.id}")
        # reports = await job.get_wms_reports(session)
        # print(reports)
        group_jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "superseded": job.superseded,
                "status": map_status(job.status),
                "data": job.data,
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
