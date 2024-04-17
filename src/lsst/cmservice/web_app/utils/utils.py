from lsst.cmservice.common.enums import StatusEnum


async def get_campaign_details(session, campaign):
    collections = await campaign.resolve_collections(session)
    jobs = await campaign.get_jobs(session)
    for j in jobs:
        print(f"{j.id} - {j.name} - {j.status}")
    campaign_details = {
        "name": campaign.name,
        "lsst_version": campaign.data["lsst_version"],
        "root": collections["root"],
        "source": collections["campaign_source"],
        "status": map_status(campaign.status),
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
