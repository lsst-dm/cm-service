"""Pydantic model for the Queue tables

This Table keeps track of Elements that are
being processed by daemons.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class QueueBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Interval between calls to process
    interval: float = 300.0
    # Options based to process
    options: dict | str | None = None


class QueueCreate(QueueBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Fullname of associated Element
    fullname: str


class Queue(QueueBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int

    # element_level: int  #FIXME (for now this defaults to campaign)
    element_id: int

    # When this was added to Queue
    time_created: datetime
    # Time last call to process finished
    time_updated: datetime
    # When processing of this element completed
    time_finished: datetime | None = None


class QueueUpdate(QueueBase):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

    # Interval between calls to process
    interval: float = 300.0
    # Options based to process
    options: dict | str | None = None
    # Time last call to process finished
    time_updated: datetime
    # When processing of this element completed
    time_finished: datetime | None = None
