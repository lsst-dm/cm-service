from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Production(Base):
    __tablename__ = "production"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
