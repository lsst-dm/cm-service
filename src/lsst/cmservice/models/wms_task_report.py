from pydantic import BaseModel


class WmsTaskReportBase(BaseModel):
    job_id: int
    name: str
    fullname: str

    n_unknown: int
    n_misfit: int
    n_unready: int
    n_ready: int
    n_pending: int
    n_running: int
    n_deleted: int
    n_held: int
    n_succeeded: int
    n_failed: int
    n_pruned: int


class WmsTaskReportCreate(WmsTaskReportBase):
    """Parameters that are used to create new rows but not in DB tables"""


class WmsTaskReport(WmsTaskReportBase):
    id: int

    class Config:
        orm_mode = True
