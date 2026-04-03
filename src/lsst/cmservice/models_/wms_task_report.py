from pydantic import BaseModel, ConfigDict


class WmsTaskReportBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

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
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    id: int


class WmsTaskReportUpdate(WmsTaskReportBase):
    """Parameters that can be udpated"""

    model_config = ConfigDict(from_attributes=True)

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
