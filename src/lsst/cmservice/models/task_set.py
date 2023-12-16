"""Pydantic model for the ProductSet tables

These are used to keep track of pipetasks associated
to workflows.

These tables are populated with the output
of pipetask report
"""

from pydantic import BaseModel


class TaskSetBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Name of the Pipetask
    name: str

    # ForiegnKey giving associated Job
    job_id: int

    # Number of expected quanta run in the workflow
    n_expected: int


class TaskSetCreate(TaskSetBase):
    """Parameters that are used to create new rows but not in DB tables"""


class TaskSet(TaskSetBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # Primary Key
    id: int

    # Unique Name for the combination of Job/Task
    fullname: str

    # Number of quanta run sucessfully
    n_done: int = 0
    # Number of quanta that failed
    n_failed: int = 0
    # Number of quanta did not run b/c of upstream failures
    n_failed_upstream: int = 0

    class Config:
        orm_mode = True


class TaskSetUpdate(TaskSetBase):
    """Parameters that can be udpated"""

    # Number of expected quanta run in the workflow
    n_expected: int
    # Number of quanta run sucessfully
    n_done: int = 0
    # Number of quanta that failed
    n_failed: int = 0
    # Number of quanta did not run b/c of upstream failures
    n_failed_upstream: int = 0

    class Config:
        orm_mode = True
