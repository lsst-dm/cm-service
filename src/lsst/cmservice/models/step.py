from pydantic import BaseModel


class StepBase(BaseModel):
    campaign: int
    name: str


class StepCreate(StepBase):
    pass


class Step(StepBase):
    id: int

    class Config:
        orm_mode = True
