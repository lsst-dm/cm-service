from pydantic import BaseModel


class GroupBase(BaseModel):
    step: int
    name: str


class GroupCreate(GroupBase):
    pass


class Group(GroupBase):
    id: int

    class Config:
        orm_mode = True
