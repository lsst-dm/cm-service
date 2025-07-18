"""Pydantic model for the StepDependency and ScriptDependency
database classes.

These are classes that track processing dependencies
between Steps and Scripts, respectively.

In each case the 'prerequisite' Node must run before the 'dependent' Node
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DependencyBase(BaseModel):
    """Parameters that are in DB tables and also used to create new rows"""

    # ForeignKey for the prerequiste
    prereq_id: int
    # ForiegnKey for the dependency
    depend_id: int
    namespace: UUID | None = Field(default=None)


class DependencyCreate(DependencyBase):
    """Parameters that are used to create new rows but not in DB tables"""


class Dependency(DependencyBase):
    """Parameters that are in DB tables and not used to create new rows"""

    model_config = ConfigDict(from_attributes=True)

    # primary key
    id: int
