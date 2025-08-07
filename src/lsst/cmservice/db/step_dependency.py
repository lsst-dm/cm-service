from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy.dialects.postgresql as sapg
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import StatusEnum
from .base import Base
from .row import RowMixin

if TYPE_CHECKING:
    from ..common.types import AnyAsyncSession
    from .step import Step


class StepDependency(Base, RowMixin):
    """Database table to establish dependecy of one step on another

    A StepDependency will prevent the `depend_` entry
    from running until the `prereq_` entry is accepted
    """

    __tablename__ = "step_dependency"
    class_string = "step_dependency"

    id: Mapped[int] = mapped_column(primary_key=True)
    prereq_id: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    depend_id: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    namespace: Mapped[UUID] = mapped_column(name="namespace", type_=sapg.UUID, nullable=True, default=None)

    prereq_: Mapped[Step] = relationship("Step", viewonly=True, foreign_keys=[prereq_id])
    depend_: Mapped[Step] = relationship("Step", viewonly=True, foreign_keys=[depend_id])

    col_names_for_table = ["id", "prereq_id", "depend_id"]

    def __repr__(self) -> str:
        return f"StepDependency {self.prereq_id}: {self.depend_id}"

    async def is_done(
        self,
        session: AnyAsyncSession,
    ) -> bool:
        """Check if this dependency is completed

        Parameters
        ----------
        session : AnyAsyncSession
            DB session manager

        Returns
        -------
        done: bool
            Returns True if the prerequisite is done
        """
        await session.refresh(self, attribute_names=["prereq_"])
        if self.prereq_.status.value >= StatusEnum.accepted.value:
            return True
        return False
