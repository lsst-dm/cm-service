from pydantic import BaseModel

from ..common.enums import StatusEnum


class ElementBase(BaseModel):
    name: str
    data: dict | str | None = None
    child_config: dict | str | None = None
    collections: dict | str | None = None
    spec_aliases: dict | str | None = None
    handler: str | None = None


class ElementCreateMixin(ElementBase):
    spec_block_name: str
    parent_name: str


class ElementMixin(ElementBase):
    id: int
    spec_block_id: int
    parent_id: int
    fullname: str
    status: StatusEnum = StatusEnum.waiting
    superseded: bool = False

    class Config:
        orm_mode = True


class Element(ElementMixin):
    pass
