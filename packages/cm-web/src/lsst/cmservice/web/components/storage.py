from __future__ import annotations

from typing import Annotated, Any

from nicegui import app
from pydantic import BaseModel, Field, PlainSerializer


class StorageModel(BaseModel):
    """A base model for storage models. This model is configured to allow extra
    fields of arbitrary types beyond those defined in specific child models.
    """

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


class ClientStorageModel(StorageModel):
    """This model describes the contents of managed CLIENT storage, including
    the pass-through wrapper to USER storage via the `user` attribute.
    """

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
    """This model describes the contents of managed USER storage, especially
    when used with the `UserStorageWrapper`.

    User storage must be serializable data.
    """

    username: str = Field(
        default="anonymous", description="The name of the current user as understood from the request header."
    )
    favorites: Annotated[set, PlainSerializer(lambda x: list(x), return_type=list)] = Field(
        default_factory=set,
        description="A set of IDs that have been marked as user favorites",
    )
    active_filters: Annotated[set, PlainSerializer(lambda x: list(x), return_type=list)] = Field(
        default_factory=set,
        description="A set of active filter names or ids",
    )
    ignore_list: Annotated[set, PlainSerializer(lambda x: list(x), return_type=list)] = Field(
        default_factory=set,
        description="A set of IDs that have been marked as ignored/hidden/trashed by the user",
    )
    filtered_owners: Annotated[set, PlainSerializer(lambda x: list(x), return_type=list)] = Field(
        default_factory=set,
        description="A set of owner names that have been selected by the user in the campaign filter",
    )


class UserStorageWrapper:
    """This wrapper provides access to USER storage from another model insstead
    of separately accessing `app.storage.user` and `app.storage.*`.
    """

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

    "CLIENT" storage differs from "USER" storage: this schema is constructed
    for each client connection and is ephemeral. It may be used for page/
    subpage cache information and does not require serializable data types.

    The `ClientStorageModel` has a *pass-through* wrapper to access "USER"
    storage via the `.user` atttribute.

    This method creates a singleton `ClientStorageModel` as the "state" key
    in the standard app client storage. Any page using this storage may call
    this method during setup to ensure its initialization.
    """
    if "state" not in app.storage.client:
        app.storage.client["state"] = ClientStorageModel(user=UserStorageWrapper())
