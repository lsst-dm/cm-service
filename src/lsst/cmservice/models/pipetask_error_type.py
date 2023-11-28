from pydantic import BaseModel

from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum


class PipetaskErrorTypeBase(BaseModel):
    source: ErrorSourceEnum
    flavor: ErrorFlavorEnum
    action: ErrorActionEnum
    task_name: str
    diagnostic_message: str


class PipetaskErrorTypeCreate(PipetaskErrorTypeBase):
    pass


class PipetaskErrorType(PipetaskErrorTypeBase):
    id: int

    class Config:
        orm_mode = True
