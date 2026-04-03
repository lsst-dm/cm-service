from __future__ import annotations

import enum
from uuid import NAMESPACE_DNS, uuid5

DEFAULT_NAMESPACE = uuid5(NAMESPACE_DNS, "io.lsst.cmservice")
"""A default UUID5 namespace to use throughout the application."""


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
    # Legacy kinds
    specification = enum.auto()
    spec_block = enum.auto()
    job = enum.auto()
    script = enum.auto()
    # Library Kinds
    lsst = enum.auto()
    bps = enum.auto()
    butler = enum.auto()
    wms = enum.auto()
    site = enum.auto()
    # Fallback kind
    other = enum.auto()
    dummy = enum.auto()


class StatusEnum(enum.Enum):
    """Keeps track of the status of a particular script or entry

    Typically these should move from `waiting` to `accepted`
    one step at a time.

    Bad States, requires intervention:
    blocked = -5  # The job is held or unready in the WMS
    failed = -4  # Processing failed
    rejected = -3  # Marked as rejected
    paused = -2 # processing is paused for some reason
    rescuable = -1  # Failed, but in a way where a rescue is possible

    Processing states and the transitions between them:

    waiting = 0  # Prerequisites not ready
       If all the prerequisites are `accepted` can move to `ready`

    ready = 1  # Ready to run
       Prerequistes are done, script is not written or children are
       not created.

    prepared = 2  # Inputs are being prepared
       Script or function is ready, children are created,
       processing can be launched

    running = 3  # Element is running
       Script or function is running or children are processing

    reviewable = 4  # Output is ready to review
       Many scripts and functions will skip this step

    accepted = 5  # Completed, reviewed and accepted

    rescued = 6 # Rescueable and rescued

    Note that the 'rescuable' and 'rescued' states do
    not apply to scripts, only Elements
    """

    # note that ordering of these Enums matters within the code matters.
    overdue = -6
    failed = -5
    rejected = -4
    blocked = -3
    paused = -2
    rescuable = -1  # Scripts are not rescuable
    waiting = 0
    ready = 1
    prepared = 2
    running = 3
    # For scripts, status with value greater or equal to reviewable should be
    # considered a terminal state
    reviewable = 4
    # For elements states with value greater or equal to accepted should be
    # considered a terminal state
    accepted = 5
    rescued = 6  # Scripts can not be rescued

    def is_successful_element(self) -> bool:
        """Is this successful state for Elements"""
        return self.value >= StatusEnum.accepted.value

    def is_successful_script(self) -> bool:
        """Is this successful state for Script"""
        return self.value >= StatusEnum.accepted.value

    def is_bad(self) -> bool:
        """Is this a failed state"""
        return self.value <= StatusEnum.rejected.value

    def is_terminal_element(self) -> bool:
        """Is this element in any terminal state"""
        return any(
            [
                self.is_successful_element(),
                self.is_bad(),
            ]
        )

    def is_terminal_script(self) -> bool:
        """Is this script in any terminal state"""
        return any(
            [
                self.is_successful_script(),
                self.is_bad(),
                self is StatusEnum.reviewable,
            ]
        )

    def is_processable_element(self) -> bool:
        """Is this a processable state for an element"""
        return self.value >= StatusEnum.waiting.value and self.value <= StatusEnum.reviewable.value

    def is_processable_script(self) -> bool:
        """Is this a processable state for a script"""
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
