from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import ForeignKey, UniqueConstraint

from .base import Base


class Campaign(Base):
    __tablename__ = "campaign"
    __table_args__ = (UniqueConstraint("production", "name"),)  # Name must be unique within parent production

    id: Mapped[int] = mapped_column(primary_key=True)
    production: Mapped[int] = mapped_column(ForeignKey("production.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(index=True)
