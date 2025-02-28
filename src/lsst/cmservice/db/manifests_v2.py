from sqlmodel import Field, SQLModel


# this can probably be a BaseModel since this is not a db relation, but the
# distinction probably doesn't matter
class ManifestWrapper(SQLModel):
    """a model for an object's Manifest wrapper, used by APIs where the `spec`
    should be the kind's table model, more or less.
    """

    apiversion: str = Field(default="io.lsst.cmservice/v1")
    kind: str
    metadata_: dict
    spec: dict
