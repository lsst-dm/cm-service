"""Pydantic model for the ProductSet tables

These are used to keep track of files
produced by workflows and stored in the butler.

These tables are populated with the output
of pipetask report
"""

from pydantic import BaseModel


class ProductSetBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # Type of data product
    name: str
    # ForeignKey to the associated Job
    job_id: int
    # ForeignKey to the associated TaskSet
    task_id: int
    # Number of files of this type expected for this task
    n_expected: int


class ProductSetCreate(ProductSetBase):
    """Parameters that are used to create new rows but not in DB tables"""


class ProductSet(ProductSetBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # Primary Key
    id: int
    # Unique Name for the combination of Job/Task/File
    fullname: str

    # Number of files produced
    n_done: int = 0
    # Number of files not produced because the task failed
    n_failed: int = 0
    # Number of files not produced because of upstream failures
    n_failed_upstream: int = 0
    # Number of files missing
    n_missing: int = 0

    class Config:
        orm_mode = True
