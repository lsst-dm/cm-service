from pydantic import BaseModel


class ScriptTemplateBase(BaseModel):
    spec_id: int
    name: str
    data: dict | list | None


class ScriptTemplateCreate(ScriptTemplateBase):
    spec_name: str


class ScriptTemplate(ScriptTemplateBase):
    id: int
    spec_id: int
    fullname: str

    class Config:
        orm_mode = True
