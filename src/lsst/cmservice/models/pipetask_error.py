from pydantic import BaseModel


class PipetaskErrorBase(BaseModel):
    error_type_id: int | None = None
    task_id: int
    quanta: str
    diagnostic_message: str
    data_id: dict


class PipetaskErrorCreate(PipetaskErrorBase):
    pass


class PipetaskError(PipetaskErrorBase):
    id: int

    class Config:
        orm_mode = True
