"""Pydantic model for the PipetaskError tables

These tables represent errors reported
by pipetask report.

These are errors associated to processing
specific quanta.
"""

from pydantic import BaseModel


class PipetaskErrorBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # ForeignKey into PipetaskErrorType table
    # None means that the error in not yet identified
    error_type_id: int | None = None

    # ForiegnKey into TaskSet table
    task_id: int

    # UUID for the quanta that had the error
    quanta: str

    # Diagnostic message produced by the error
    diagnostic_message: str

    # Data ID for the quanta that had the error
    data_id: dict


class PipetaskErrorCreate(PipetaskErrorBase):
    """Parameters that are used to create new rows but not in DB tables"""


class PipetaskError(PipetaskErrorBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # Primary Key
    id: int

    class Config:
        orm_mode = True


class PipetaskErrorUpdate(PipetaskErrorBase):
    """Parameters that can be udpated"""

    # ForeignKey into PipetaskErrorType table
    # None means that the error in not yet identified
    error_type_id: int | None = None

    # UUID for the quanta that had the error
    quanta: str

    # Diagnostic message produced by the error
    diagnostic_message: str

    # Data ID for the quanta that had the error
    data_id: dict

    class Config:
        orm_mode = True
