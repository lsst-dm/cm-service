from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from .base import Base


class Step(Base):
    __tablename__ = "step"
    __table_args__ = (UniqueConstraint("campaign", "name"),)  # Name must be unique within parent campaign

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign: Mapped[int] = mapped_column(ForeignKey("campaign.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
