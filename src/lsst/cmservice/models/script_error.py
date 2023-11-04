from pydantic import BaseModel


class ScriptErrorBase(BaseModel):
    script_id: int
    source: int
    diagnostic_message: str


class ScriptErrorCreate(ScriptErrorBase):
    pass


class ScriptError(ScriptErrorBase):
    id: int

    class Config:
        orm_mode = True
