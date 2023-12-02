from pydantic import BaseModel


class ProductSetBase(BaseModel):
    name: str
    job_id: int
    task_id: int
    n_expected: int


class ProductSetCreate(ProductSetBase):
    pass


class ProductSet(ProductSetBase):
    id: int
    fullname: str

    n_done: int = 0
    n_failed: int = 0
    n_failed_upstream: int = 0
    n_missing: int = 0

    class Config:
        orm_mode = True
