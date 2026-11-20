from enum import Enum, IntEnum, auto
from warnings import deprecated


@deprecated("Enum is unused in v2")
class TaskStatusEnum(IntEnum):
    """Defines possible outcomes for Pipetask tasks"""

    processing = auto()
    done = auto()
    failed = auto()
    failed_upstream = auto()
    missing = auto()


@deprecated("Enum is unused in v2")
class ProductStatusEnum(IntEnum):
    """Defines possible outcomes for Pipetask Products"""

    processing = auto()
    done = auto()
    failed = auto()
    failed_upstream = auto()
    missing = auto()


@deprecated("Enum is unused in v2")
class ErrorSourceEnum(IntEnum):
    """Who first reported the error"""

    cmservice = auto()
    local_script = auto()
    htc_workflow = auto()
    manifest = auto()


@deprecated("Enum is unused in v2")
class ErrorFlavorEnum(IntEnum):
    """What sort of error are we talking about"""

    infrastructure = auto()
    configuration = auto()
    pipelines = auto()


@deprecated("Enum is unused in v2")
class ErrorActionEnum(IntEnum):
    """What should we do about it?"""

    fail = auto()
    requeue_and_pause = auto()
    rescue = auto()
    auto_retry = auto()
    review = auto()
    accept = auto()


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
