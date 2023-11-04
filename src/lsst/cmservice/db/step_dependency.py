from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import ForeignKey

from ..common.enums import LevelEnum, StatusEnum
from .base import Base
from .dbid import DbId
from .row import RowMixin

if TYPE_CHECKING:
    from .step import Step


class StepDependency(Base, RowMixin):
    """Database table to establish dependecy of one step on another

    A StepDependency will prevent the `depend_` entry
    from running until the `prereq_` entry is accepted
    """

    __tablename__ = "step_dependency"

    id: Mapped[int] = mapped_column(primary_key=True)
    prereq_id: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    depend_id: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)

    prereq_: Mapped["Step"] = relationship("Step", viewonly=True, foreign_keys=[prereq_id])
    depend_: Mapped["Step"] = relationship("Step", viewonly=True, foreign_keys=[depend_id])

    @hybrid_property
    def prereq_db_id(self) -> DbId:
        return DbId(LevelEnum.step, self.prereq_id)

    @hybrid_property
    def depend_db_id(self) -> DbId:
        return DbId(LevelEnum.step, self.depend_id)

    def __repr__(self) -> str:
        return f"StepDependency {self.prereq_db_id}: {self.depend_db_id}"

    async def is_done(
        self,
        session: async_scoped_session,
    ) -> bool:
        """Check if this dependency is completed

        Parameters
        ----------
        session : async_scoped_session
            DB session manager

        Returns
        -------
        done: bool
            Returns True if the prerequisite is done
        """
        async with session.begin_nested():
            await session.refresh(self, attribute_names=["prereq_"])
            if self.prereq_.status.value >= StatusEnum.accepted.value:
                return True
            return False
