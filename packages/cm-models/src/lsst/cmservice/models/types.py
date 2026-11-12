from typing import Annotated

from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionSA
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlmodel.ext.asyncio.session import AsyncSession as AsyncSession

from .enums import AuditActionEnum, ManifestKind, NotificationLabelEnum, StatusEnum
from .serde import (
    AuditActionEnumValidator,
    EnumSerializer,
    ManifestKindEnumValidator,
    NotificationLabelEnumValidator,
    StatusEnumValidator,
    TemplateExpressionsValidator,
)

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


type ActionField = Annotated[AuditActionEnum, AuditActionEnumValidator, EnumSerializer]
"""A type for fields representing an Action with a custom validator tuned for
enums operations.
"""


type NotificationLabelKindField = Annotated[
    NotificationLabelEnum, NotificationLabelEnumValidator, EnumSerializer
]
"""A type for fields representing a Notification Label with a custom validator
tuned for enums operations.
"""


type TemplateExpressions = Annotated[dict[str, str], TemplateExpressionsValidator]
"""A type for fields representing a mapping of template variable names to
string representations of valid Python expressions.

Each expression is evaluated in a sandbox when a Schedule creates a new
campaign, and its result is available to the campaign's templates as a variable
of the same name.
"""
