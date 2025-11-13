from ...common.enums import StatusEnum

TRANSITIONS = [
    # The critical/happy path of state evolution from waiting to accepted
    {
        "trigger": "prepare",
        "source": StatusEnum.waiting,
        "dest": StatusEnum.ready,
    },
    {
        "trigger": "start",
        "source": StatusEnum.ready,
        "dest": StatusEnum.running,
        "conditions": "is_startable",
    },
    {
        "trigger": "finish",
        "source": StatusEnum.running,
        "dest": StatusEnum.accepted,
        "conditions": "is_done_running",
    },
    # The bad transitions
    {"trigger": "block", "source": StatusEnum.running, "dest": StatusEnum.blocked},
    {
        "trigger": "fail",
        "source": [StatusEnum.waiting, StatusEnum.ready, StatusEnum.running],
        "dest": StatusEnum.failed,
    },
    # User-initiated transitions
    {"trigger": "pause", "source": StatusEnum.running, "dest": StatusEnum.paused},
    {"trigger": "unblock", "source": StatusEnum.blocked, "dest": StatusEnum.running},
    {"trigger": "resume", "source": StatusEnum.paused, "dest": StatusEnum.running},
    {"trigger": "force", "source": StatusEnum.failed, "dest": StatusEnum.accepted},
    # Inverse transitions, i.e., rollbacks
    {"trigger": "unprepare", "source": StatusEnum.ready, "dest": StatusEnum.waiting},
    {"trigger": "stop", "source": StatusEnum.paused, "dest": StatusEnum.ready},
    {"trigger": "retry", "source": StatusEnum.failed, "dest": StatusEnum.ready},
    {"trigger": "restart", "source": StatusEnum.failed, "dest": StatusEnum.ready, "conditions": "is_restartable"},
    {"trigger": "reset", "source": StatusEnum.failed, "dest": StatusEnum.waiting},
]
"""Transitions available to a Node, expressed as source-destination pairs
with a named trigger-verb.
"""
