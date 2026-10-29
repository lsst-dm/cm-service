import enum
from functools import total_ordering
from uuid import NAMESPACE_DNS, uuid5

DEFAULT_NAMESPACE = uuid5(NAMESPACE_DNS, "io.lsst.cmservice")
"""A default UUID5 namespace to use throughout the application."""


@total_ordering
class ManifestKind(enum.Enum):
    """Define a manifest kind"""

    campaign = enum.auto()
    node = enum.auto()
    edge = enum.auto()
    # Node kinds
    start = enum.auto()
    step = enum.auto()
    group = enum.auto()
    collect_groups = enum.auto()
    breakpoint = enum.auto()
    end = enum.auto()
    # Library Kinds
    lsst = enum.auto()
    bps = enum.auto()
    butler = enum.auto()
    wms = enum.auto()
    site = enum.auto()
    artifact = enum.auto()
    # Fallback kind
    other = enum.auto()
    dummy = enum.auto()
    # Misc Task kinds
    schedule = enum.auto()
    template = enum.auto()
    notification_label = enum.auto()

    def __lt__(self, other: ManifestKind) -> bool:
        """Implements a simple "rich" less-than operator for simple ordering
        based on the (arbitrary) value of each member. This is primarily used
        for sorting and grouping operations, not necessarily for semantic
        comparison.

        Note: the `@total_ordering` decorator adds all other rich comparison
        methods.
        """
        if not isinstance(other, ManifestKind):
            return NotImplemented
        return self.value < other.value


class StatusEnum(enum.Enum):
    """Keep track of the status of a campaign or node

    Typically these should move from `waiting` to `accepted`
    one step at a time.

    Bad States, requires intervention:
    - `overdue`: The job has been running past its deadline
    - `blocked`: The job is held or unready in the WMS
    - `failed`: Processing failed
    - `rejected`: Marked as rejected
    - `paused`: processing is paused for some reason

    Processing states and the transitions between them:

    - `waiting`: Prerequisites not ready
       If all the prerequisites are `accepted` can move to `ready`

    - `ready`: Ready to run; prerequistes are done and artifacts are written

    - `running` : Job is running, or a breakpoint is waiting for clearance

    - `accepted`: Completed, reviewed and successful
    - `failed`: Completed, but has failed
    """

    # note that ordering of these Enums matters within the code matters.
    overdue = -6
    failed = -5
    rejected = -4
    blocked = -3
    paused = -2
    waiting = 0
    ready = 1
    running = 3
    reviewable = 4
    accepted = 5

    def is_successful(self) -> bool:
        """Check if the status is a terminal positive result"""
        return self.value >= StatusEnum.accepted.value

    def is_bad(self) -> bool:
        """Check if the status is a terminal negative result"""
        return self.value <= StatusEnum.rejected.value

    def is_terminal(self) -> bool:
        """Check if the status is a terminal state"""
        return any(
            [
                self.is_successful(),
                self.is_bad(),
                self is StatusEnum.reviewable,
            ]
        )

    def is_processable(self) -> bool:
        """Check whether the state allows transitions behavior"""
        return self.value >= StatusEnum.waiting.value and self.value <= StatusEnum.running.value

    def next_status(self) -> StatusEnum:
        """If the status is on the "happy" path, return the next status along
        that path, otherwise return the failed status.
        """
        happy_path = [StatusEnum.waiting, StatusEnum.ready, StatusEnum.running, StatusEnum.accepted]
        if self in happy_path:
            i = happy_path.index(self)
            next_index = min(i + 1, len(happy_path) - 1)
            return happy_path[next_index]
        else:
            return StatusEnum.failed


class AuditActionEnum(enum.Enum):
    """Available actions for audit log entries."""

    create = enum.auto()
    read = enum.auto()
    update = enum.auto()
    delete = enum.auto()


class NotificationLabelEnum(enum.Enum):
    """Available label kinds for notification events."""

    default = enum.auto()
    kafka = enum.auto()
    slack = enum.auto()
