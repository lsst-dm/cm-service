from .element import ElementCreateMixin, ElementMixin


class CampaignCreate(ElementCreateMixin):
    pass


class Campaign(ElementMixin):
    class Config:
        orm_mode = True
