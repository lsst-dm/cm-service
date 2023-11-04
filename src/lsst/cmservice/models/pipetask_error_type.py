from pydantic import BaseModel

from ..common.enums import ErrorAction, ErrorFlavor, ErrorSource


class PipetaskErrorTypeBase(BaseModel):
    source: ErrorSource
    flavor: ErrorFlavor
    action: ErrorAction
    task_name: str
    diagnostic_message: str


class PipetaskErrorTypeCreate(PipetaskErrorTypeBase):
    pass


class PipetaskErrorType(PipetaskErrorTypeBase):
    id: int

    class Config:
        orm_mode = True
