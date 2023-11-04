from pydantic import BaseModel


class SpecBlockBase(BaseModel):
    spec_id: int
    name: str
    handler: str | None = None
    data: dict | list | None
    collections: dict | list | None
    child_config: dict | list | None
    spec_aliases: dict | list | None
    scripts: dict | list | None


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
