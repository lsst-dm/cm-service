from enum import Enum, IntEnum, auto


class TaskStatusEnum(IntEnum):
    """Defines possible outcomes for Pipetask tasks"""

    processing = auto()
    done = auto()
    failed = auto()
    failed_upstream = auto()
    missing = auto()


class ProductStatusEnum(IntEnum):
    """Defines possible outcomes for Pipetask Products"""

    processing = auto()
    done = auto()
    failed = auto()
    failed_upstream = auto()
    missing = auto()


class ErrorSourceEnum(IntEnum):
    """Who first reported the error"""

    cmservice = auto()
    local_script = auto()
    htc_workflow = auto()
    manifest = auto()


class ErrorFlavorEnum(IntEnum):
    """What sort of error are we talking about"""

    infrastructure = auto()
    configuration = auto()
    pipelines = auto()


class ErrorActionEnum(IntEnum):
    """What should we do about it?"""

    fail = auto()
    requeue_and_pause = auto()
    rescue = auto()
    auto_retry = auto()
    review = auto()
    accept = auto()


class WmsMethodEnum(IntEnum):
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

    default = auto()
    bash = auto()
    panda = auto()
    htcondor = auto()


class WmsComputeSite(IntEnum):
    """Define a potential compute site"""

    default = auto()
    slac = auto()
    lancs = auto()
    ral = auto()
    in2p3 = auto()


class SplitterEnum(Enum):
    """An enumeration of supported splitter kinds where the value is the string
    constant used in the Node configuration.
    """

    NULL = "null"
    QUERY = "query"
    VALUES = "values"
