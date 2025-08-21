"""Pydantic model for the Queue tables

This Table keeps track of Elements that are
being processed by daemons.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..common.enums import LevelEnum


class QueueBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Interval between calls to process
    interval: float = 300.0
    # Options based to process
    options: dict | None = None
    # Whether the queue is active or paused
    active: bool = False


class QueueCreate(QueueBase):
    """Parameters that are used to create new rows but not in DB tables"""

    # Fullname of associated Element
    fullname: str | None = None

    # Id of node to add
    node_id: int | None = None

    # Which type of node to add
    node_level: int | None = None


class Queue(QueueBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # PrimaryKey
    id: int

    # When this was added to Queue
    time_created: datetime
    # Time last call to process finished
    time_updated: datetime
    # When processing of this element completed
    time_finished: datetime | None = None
    # When to next check this entry
    time_next_check: datetime | None = None
    # Id of node to add
    node_id: int
    # Which type of node to add
    node_level: LevelEnum
    # Mutable metadata dictionary for the queue
    metadata_: dict


class QueueUpdate(QueueBase):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

    # Interval between calls to process
    interval: float = 300.0
    # Options based to process
    options: dict | None = None
    # Time last call to process finished
    time_updated: datetime | None = None
    # When processing of this element completed
    time_finished: datetime | None = None
    # Mutable metadata dictionary for the queue
    metadata_: dict = Field(default_factory=dict)
