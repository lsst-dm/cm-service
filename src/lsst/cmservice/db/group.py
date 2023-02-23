from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from .base import Base


class Group(Base):
    __tablename__ = "group"
    __table_args__ = (UniqueConstraint("step", "name"),)  # Name must be unique within parent step

    id: Mapped[int] = mapped_column(primary_key=True)
    step: Mapped[int] = mapped_column(ForeignKey("step.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
