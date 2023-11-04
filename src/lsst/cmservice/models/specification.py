from typing import Optional

from pydantic import BaseModel


class SpecBlockBase(BaseModel):
    spec_id: int
    name: str
    handler: str | None = None
    data: Optional[dict | list]
    collections: Optional[dict | list]
    child_config: Optional[dict | list]
    spec_aliases: Optional[dict | list]
    scripts: Optional[dict | list]


class SpecBlockCreate(SpecBlockBase):
    spec_name: str


class SpecBlock(SpecBlockBase):
    id: int
    spec_id: int
    fullname: str

    class Config:
        orm_mode = True


class SpecificationBase(BaseModel):
    name: str


class SpecificationCreate(SpecificationBase):
    pass


class Specification(SpecificationBase):
    id: int

    class Config:
        orm_mode = True


class SpecificationLoad(BaseModel):
    spec_name: str = "example"
    yaml_file: str = "examples/example_config.yaml"
