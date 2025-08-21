from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionSA
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSession

from .. import models
from ..models.serde import EnumSerializer, ManifestKindEnumValidator, StatusEnumValidator
from .enums import ManifestKind, StatusEnum

type AnyAsyncSession = AsyncSession | AsyncSessionSA | async_scoped_session
"""A type union of async database sessions the application may use"""


type AnyCampaignElement = models.Group | models.Campaign | models.Step | models.Job
"""A type union of Campaign elements"""


type StatusField = Annotated[StatusEnum, StatusEnumValidator, EnumSerializer]
"""A type for fields representing a Status with a custom validator tuned for
enums operations.
"""


type KindField = Annotated[ManifestKind, ManifestKindEnumValidator, EnumSerializer]
"""A type for fields representing a Kind with a custom validator tuned for
enums operations.
"""
