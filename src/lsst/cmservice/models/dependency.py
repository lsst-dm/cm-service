from pydantic import BaseModel


class DependencyBase(BaseModel):
    prereq_id: int
    depend_id: int


class DependencyCreate(DependencyBase):
    pass


class Dependency(DependencyBase):
    id: int

    class Config:
        orm_mode = True
