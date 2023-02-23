from pydantic import BaseModel


class CampaignBase(BaseModel):
    production: int
    name: str


class CampaignCreate(CampaignBase):
    pass


class Campaign(CampaignBase):
    id: int

    class Config:
        orm_mode = True
