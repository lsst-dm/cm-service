from __future__ import annotations

from typing import Annotated, Any

from nicegui import app
from pydantic import BaseModel, Field, PlainSerializer


class StorageModel(BaseModel):
    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


class ClientStorageModel(StorageModel):
    campaigns: dict[str, dict] = Field(
        default_factory=dict,
        description="A cache of loaded campaigns",
    )
    nodes: dict[str, dict] = Field(
        default_factory=dict,
        description="A cache of loaded nodes",
    )
    user: UserStorageWrapper


class UserStorageModel(StorageModel):
    favorites: Annotated[set, PlainSerializer(lambda x: list(x), return_type=list)] = Field(
        default_factory=set,
        description="A set of IDs that have been marked as user favorites",
    )


class UserStorageWrapper:
    key: str = "user"
    model_class: type[StorageModel] = UserStorageModel

    def __init__(self) -> None:
        if self.key not in app.storage.user:
            app.storage.user[self.key] = {}

    def _get(self) -> StorageModel:
        data = app.storage.user.get(self.key, {})
        return self.model_class(**data)

    def _update(self, data: StorageModel) -> None:
        app.storage.user[self.key] = data.model_dump()

    def __getattr__(self, name: str) -> Any:
        data = self._get()
        return getattr(data, name)

    def __setattr__(self, name: str, value: Any) -> None:
        data = self._get()
        setattr(data, name, value)
        self._update(data)


def initialize_client_storage() -> None:
    """Function initializes server-side in-memory client storage.

    This schema is constructed for each client connection and is ephemeral. It
    may be used for page/subpage cache information and does not require serial-
    izable data types.
    """
    if "state" not in app.storage.client:
        app.storage.client["state"] = ClientStorageModel(user=UserStorageWrapper())
