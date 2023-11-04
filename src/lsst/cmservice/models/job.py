from .element import ElementBase, ElementCreateMixin, ElementMixin


class JobBase(ElementBase):
    attempt: int = 0
    wms_job_id: int | None = None
    stamp_url: str | None = None


class JobCreate(JobBase, ElementCreateMixin):
    pass


class Job(JobBase, ElementMixin):
    pass
