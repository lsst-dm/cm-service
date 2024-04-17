from lsst.cmservice.common.enums import StatusEnum


async def get_campaign_details(session, campaign):
    collections = await campaign.resolve_collections(session)
    jobs = await campaign.get_jobs(session)
    jobs_completed = [job for job in jobs if job.status == StatusEnum.accepted]
    scripts = await campaign.get_scripts(session)
    scripts_completed = [script for script in scripts if script.status == StatusEnum.accepted]
    #     steps = await campaign.children(session)
    #     for s in steps:
    #         print(f"{s.id} - {s.name} - {s.status}")
    campaign_details = {
        "name": campaign.name,
        "lsst_version": campaign.data["lsst_version"],
        "root": collections["root"],
        "source": collections["campaign_source"],
        "status": map_status(campaign.status),
        "jobs_completed": f"{len(jobs_completed)} of {len(jobs)} jobs completed",
        "scripts_completed": f"{len(scripts_completed)} of {len(scripts)} scripts completed",
    }
    return campaign_details


def map_status(status):
    match status:
        case StatusEnum.failed | StatusEnum.rejected:
            return "FAILED"
        case StatusEnum.paused:
            return "NEED_ATTENTION"
        case StatusEnum.running | StatusEnum.waiting | StatusEnum.ready:
            return "IN_PROGRESS"
        case StatusEnum.accepted | StatusEnum.reviewable:
            return "COMPLETE"
