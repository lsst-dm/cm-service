from datetime import datetime

from pydantic import BaseModel


class QueueBase(BaseModel):
    interval: float = 300.0
    options: dict | str | None = None


class QueueCreate(QueueBase):
    fullname: str


class Queue(QueueBase):
    id: int

    element_level: int
    element_id: int

    time_created: datetime
    time_updated: datetime
    time_finished: datetime | None

    class Config:
        orm_mode = True
