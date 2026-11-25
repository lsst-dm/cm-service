from collections.abc import AsyncGenerator
from typing import Annotated, Protocol

from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessionSA
from sqlalchemy.ext.asyncio import async_scoped_session, async_sessionmaker
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


class DatabaseManagerProtocol(Protocol):
    """A protocol describing the interface of a DatabaseManager used by CM"""

    sessionmaker: async_sessionmaker[AsyncSession] | None

    def __call__(self) -> AsyncGenerator[AsyncSession]: ...
    async def aclose(self) -> None: ...


class ScheduleTriggerSubjectProtocol(Protocol):
    """A protocol describing the interface of a subject message recived or
    consumed by a schedule trigger, e.g., a Kafka ``Message``.
    """

    def value(self) -> bytes | None: ...
    def topic(self) -> str | None: ...


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
