from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionSA
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSession

from .enums import ManifestKind, StatusEnum
from .serde import EnumSerializer, ManifestKindEnumValidator, StatusEnumValidator

type AnyAsyncSession = AsyncSession | AsyncSessionSA | async_scoped_session
"""A type union of async database sessions the application may use"""


type StatusField = Annotated[StatusEnum, StatusEnumValidator, EnumSerializer]
"""A type for fields representing a Status with a custom validator tuned for
enums operations.
"""


type KindField = Annotated[ManifestKind, ManifestKindEnumValidator, EnumSerializer]
"""A type for fields representing a Kind with a custom validator tuned for
enums operations.
"""
