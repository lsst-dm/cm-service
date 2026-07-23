from uuid import UUID

from pydantic import BaseModel


class NotificationPayload(BaseModel):
    id: UUID
    label: str
