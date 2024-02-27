from collections.abc import Iterable
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..common.enums import LevelEnum
from .base import Base
from .dbid import DbId
from .row import RowMixin

if TYPE_CHECKING:
    from .campaign import Campaign


class Production(Base, RowMixin):
    """Database table to associated a set of related `Campaign`s"""

    __tablename__ = "production"
    class_string = "production"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)

    c_: Mapped[list["Campaign"]] = relationship("Campaign", viewonly=True)

    col_names_for_table = ["id", "name"]

    @hybrid_property
    def db_id(self) -> DbId:
        """Returns DbId"""
        return DbId(LevelEnum.production, self.id)

    @property
    def level(self) -> LevelEnum:
        """Returns LevelEnum.production"""
        return LevelEnum.production

    @hybrid_property
    def fullname(self) -> str:
        """Maps name to fullname for consistency"""
        return self.name

    def __repr__(self) -> str:
        return f"Production {self.name} {self.id}"

    async def children(
        self,
        session: async_scoped_session,
    ) -> Iterable:
        """Maps self.c_ to self.children() for consistency"""
        await session.refresh(self, attribute_names=["c_"])
        return self.c_
