"""Pydantic model for the PipetaskErrorType tables

These are used to classify the errors
reported by pipetask report.

A PipetaskError is considered to match a PipetaskErrorType
if the diagnostic_message matches the regexp defined
in the PipetaskErrorType AND the task_name also matches
"""

from pydantic import BaseModel

from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum


class PipetaskErrorTypeBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Who reported this error
    source: ErrorSourceEnum

    # What sort of error is this
    flavor: ErrorFlavorEnum

    # What action should we take
    action: ErrorActionEnum

    # What Pipetask is this error tpye associated to
    task_name: str

    # A regexp to define this error type
    diagnostic_message: str


class PipetaskErrorTypeCreate(PipetaskErrorTypeBase):
    """Parameters that are used to create new rows but not in DB tables"""


class PipetaskErrorType(PipetaskErrorTypeBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # PrimaryKey
    id: int

    class Config:
        orm_mode = True
