# pylint: disable=invalid-name
from __future__ import annotations

import enum
from uuid import NAMESPACE_DNS, uuid5

DEFAULT_NAMESPACE = uuid5(NAMESPACE_DNS, "io.lsst.cmservice")
"""A default UUID5 namespace to use throughout the application."""


class TableEnum(enum.Enum):
    """Keep track of the various tables"""

    campaign = 1
    step = 2
    group = 3
    job = 4
    script = 5
    step_dependency = 6
    script_dependency = 7
    pipetask_error_type = 8
    pipetask_error = 9
    script_error = 10
    task_set = 11
    product_set = 12
    specification = 13
    spec_block = 14
    n_tables = 16

    def is_node(self) -> bool:
        """Is this a subclass of NodeMixin"""
        return self.value in [1, 2, 3, 4, 5]

    def is_element(self) -> bool:
        """Is this a subclass of ElementMixin"""
        return self.value in [1, 2, 3, 4]


class NodeTypeEnum(enum.Enum):
    """What kind of node: element or script"""

    element = 1
    script = 5


class LevelEnum(enum.Enum):
    """Keep track of processing hierarchy

    The levels are:

    campaign = 1
        A full data processing campaign

    step = 2
        Part of a campaign that is finished before moving on

    group = 3
        A subset of data that can be processed in paralllel as part of a step

    job = 4
        A single bps workflow

    script = 5
        A script that does a particular action.  May occur off any other level
    """

    campaign = 1
    step = 2
    group = 3
    job = 4
    script = 5
    n_levels = 6

    @staticmethod
    def get_level_from_fullname(fullname: str) -> LevelEnum:
        """Parse fullname to determine Level"""
        if fullname.find("script:") == 0:
            return LevelEnum.script
        n_slash = fullname.count("/")
        return LevelEnum(n_slash + 1)


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
        return self.value >= StatusEnum.reviewable.value

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
            ]
        )

    def is_processable_element(self) -> bool:
        """Is this a processable state for an elememnt"""
        return self.value >= StatusEnum.waiting.value and self.value <= StatusEnum.reviewable.value

    def is_processable_script(self) -> bool:
        """Is this a processable state for an elememnt"""
        return self.value >= StatusEnum.waiting.value and self.value <= StatusEnum.running.value


class TaskStatusEnum(enum.Enum):
    """Defines possible outcomes for Pipetask tasks"""

    processing = 0
    done = 1
    failed = 2
    failed_upstream = 3
    missing = 4


class ProductStatusEnum(enum.Enum):
    """Defines possible outcomes for Pipetask Products"""

    processing = 0
    done = 1
    failed = 2
    failed_upstream = 3
    missing = 4


class ErrorSourceEnum(enum.Enum):
    """Who first reported the error"""

    cmservice = 0
    local_script = 1
    htc_workflow = 1
    manifest = 2


class ErrorFlavorEnum(enum.Enum):
    """What sort of error are we talking about"""

    infrastructure = 0
    configuration = 1
    pipelines = 2


class ErrorActionEnum(enum.Enum):
    """What should we do about it?"""

    fail = -4
    requeue_and_pause = -2
    rescue = -1
    auto_retry = 0
    review = 4
    accept = 5


class ScriptMethodEnum(enum.Enum):
    """Defines how to run a script

    default = -1
        Use the default method for the handler in question

    no_script = 0
        No actual script, just uses a function

    bash = 1
        Bash script, just run the script using a system call

    slurm = 2
        Use slurm to submit the script

    htcondor = 3
        Use htcondor to submit the script

    More methods to come...
    """

    default = -1
    no_script = 0
    bash = 1
    slurm = 2
    htcondor = 3


class WmsMethodEnum(enum.Enum):
    """Defines which workflow manager to use

    default = -1
        Use the default method for the handler in question

    bash = 0
        Runs under bash (i.e., plain Pipetask)

    panda = 1
        Runs under PanDA

    htcondor = 2
        Runs under HTCondor

    More methods to come...
    """

    default = -1
    bash = 0
    panda = 1
    htcondor = 2


class WmsComputeSite(enum.Enum):
    """Define a potential compute site"""

    default = -1
    usdf = 1
    lanc = 2
    ral = 3
    in2p3 = 4
