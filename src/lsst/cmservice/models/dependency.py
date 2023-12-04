"""Pydantic model for the StepDependency and ScriptDependency
database classes.

These are classes that track processing dependencies
between Steps and Scripts, respectively.

In each case the 'prerequisite' Node must run before the 'dependent' Node
"""

from pydantic import BaseModel


class DependencyBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # ForeignKey for the prerequiste
    prereq_id: int
    # ForignKey for the dependency
    depend_id: int


class DependencyCreate(DependencyBase):
    """Parameters that are used to create new rows but not in DB tables"""

    pass


class Dependency(DependencyBase):
    """Parameters that are in DB tables and not used to create new rows"""

    # primary key
    id: int

    class Config:
        orm_mode = True
