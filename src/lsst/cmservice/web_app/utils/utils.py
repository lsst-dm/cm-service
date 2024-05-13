from lsst.cmservice.common.enums import StatusEnum


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
