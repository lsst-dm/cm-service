from pydantic import BaseModel


class TaskSetBase(BaseModel):
    name: str
    job_id: int
    n_expected: int


class TaskSetCreate(TaskSetBase):
    pass


class TaskSet(TaskSetBase):
    id: int

    fullname: str
    n_done: int = 0
    n_failed: int = 0
    n_failed_upstream: int = 0

    class Config:
        orm_mode = True
