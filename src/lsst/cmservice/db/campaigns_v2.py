from datetime import datetime
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import AliasChoices, ValidationInfo, model_validator
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import PickleType
from sqlmodel import Column, Enum, Field, MetaData, SQLModel, String

from ..common.enums import ManifestKind, StatusEnum
from ..common.types import KindField, StatusField
from ..config import config

_default_campaign_namespace = uuid5(namespace=NAMESPACE_DNS, name="io.lsst.cmservice")
"""Default UUID5 namespace for campaigns"""

metadata: MetaData = MetaData(schema=config.db.table_schema)
"""SQLModel metadata for table models"""


def jsonb_column(name: str, aliases: list[str] | None = None) -> Any:
    """Constructor for a Field based on a JSONB database column.

    If provided, a list of aliases will be used to construct a pydantic
    ``AliasChoices`` object for the field's validation alias, which improves
    usability by making model validation more flexible (e.g., having "metadata"
    and "metadata_" refer to the same field).

    Additionally, the first alias in the list will be used for the model's
    serialization alias.
    """
    schema_extra = {}
    if aliases:
        schema_extra = {
            "validation_alias": AliasChoices(*aliases),
            "serialization_alias": aliases[0],
        }
    return Field(
        sa_column=Column(name, MutableDict.as_mutable(postgresql.JSONB)),
        default_factory=dict,
        schema_extra=schema_extra,
    )


# NOTES
# - model validation is not triggered when table=True
# - Every object model needs to have three flavors:
#   1. the declarative model of the object's database table
#   2. the model of the manifest when creating a new object
#   3. the model of the manifest when updating an object
#   4. a response model for APIs related to the object


class BaseSQLModel(SQLModel):
    __table_args__ = {"schema": config.db.table_schema}
    metadata = metadata


class CampaignBase(BaseSQLModel):
    """Campaigns_v2 base model, used to create new Campaign objects."""

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID
    owner: str | None = Field(default=None)
    status: StatusField | None = Field(
        default=StatusEnum.waiting,
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])


class CampaignModel(CampaignBase):
    """model used for resource creation."""

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        """Validates the model based on different types of raw inputs,
        where some default non-optional fields can be auto-populated.
        """
        if isinstance(data, dict):
            if "name" not in data:
                raise ValueError("'name' must be specified.")
            if "namespace" not in data:
                data["namespace"] = _default_campaign_namespace
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=data["name"])
        return data


class Campaign(CampaignModel, table=True):
    """Model used for database operations involving campaigns_v2 table rows"""

    __tablename__: str = "campaigns_v2"  # type: ignore[misc]

    machine: UUID | None = Field(foreign_key="machines_v2.id", default=None, ondelete="CASCADE")


class CampaignUpdate(BaseSQLModel):
    """Model representing updatable fields for a PATCH operation on a Campaign
    using RFC7396.
    """

    owner: str | None = None
    status: StatusField | None = None


class NodeBase(BaseSQLModel):
    """nodes_v2 db table"""

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID
    version: int
    kind: KindField = Field(
        default=ManifestKind.other,
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    status: StatusField | None = Field(
        default=StatusEnum.waiting,
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])


class NodeModel(NodeBase):
    """model validating class for Nodes"""

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        if isinstance(data, dict):
            if "version" not in data:
                data["version"] = 1
            if "name" not in data:
                raise ValueError("'name' must be specified.")
            if "namespace" not in data:
                data["namespace"] = _default_campaign_namespace
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=f"""{data["name"]}.{data["version"]}""")
        return data


class Node(NodeModel, table=True):
    __tablename__: str = "nodes_v2"  # type: ignore[misc]

    machine: UUID | None = Field(foreign_key="machines_v2.id", default=None, ondelete="CASCADE")


class EdgeBase(BaseSQLModel):
    """edges_v2 db table"""

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    source: UUID = Field(foreign_key="nodes_v2.id")
    target: UUID = Field(foreign_key="nodes_v2.id")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])


class EdgeModel(EdgeBase):
    """model validating class for Edges"""

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        if isinstance(data, dict):
            if "name" not in data:
                raise ValueError("'name' must be specified.")
            if "namespace" not in data:
                raise ValueError("Edges may only exist in a 'namespace'.")
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=data["name"])
        return data


class EdgeResponseModel(EdgeModel):
    source: Any
    target: Any


class Edge(EdgeModel, table=True):
    __tablename__: str = "edges_v2"  # type: ignore[misc]


class MachineBase(BaseSQLModel):
    """machines_v2 db table."""

    id: UUID = Field(primary_key=True)
    state: Any | None = Field(sa_column=Column("state", PickleType))


class Machine(MachineBase, table=True):
    """machines_v2 db table."""

    __tablename__: str = "machines_v2"  # type: ignore[misc]


class ManifestBase(BaseSQLModel):
    """manifests_v2 db table"""

    id: UUID = Field(primary_key=True)
    name: str
    version: int
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    kind: KindField = Field(
        default=ManifestKind.other,
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    spec: dict = jsonb_column("spec", aliases=["spec", "configuration", "data"])


class ManifestModel(ManifestBase):
    """model validating class for Manifests"""

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        if isinstance(data, dict):
            if "version" not in data:
                data["version"] = 1
            if "name" not in data:
                raise ValueError("'name' must be specified.")
            if "namespace" not in data:
                data["namespace"] = _default_campaign_namespace
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=f"""{data["name"]}.{data["version"]}""")
        return data


class Manifest(ManifestBase, table=True):
    __tablename__: str = "manifests_v2"  # type: ignore[misc]


class Task(BaseSQLModel, table=True):
    """tasks_v2 db table"""

    __tablename__: str = "tasks_v2"  # type: ignore[misc]

    id: UUID = Field(primary_key=True)
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    node: UUID = Field(foreign_key="nodes_v2.id")
    priority: int
    created_at: datetime
    last_processed_at: datetime
    finished_at: datetime
    wms_id: str
    site_affinity: list[str] = Field(
        sa_column=Column("site_affinity", MutableList.as_mutable(postgresql.ARRAY(String())))
    )
    status: StatusField = Field(
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    previous_status: StatusField = Field(
        sa_column=Column(
            "previous_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )


class ActivityLogBase(BaseSQLModel):
    id: UUID = Field(primary_key=True)
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    node: UUID = Field(foreign_key="nodes_v2.id")
    operator: str
    to_status: StatusField = Field(
        sa_column=Column(
            "to_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    from_status: StatusField = Field(
        sa_column=Column(
            "from_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    detail: dict = jsonb_column("detail")


class ActivityLog(ActivityLogBase, table=True):
    __tablename__: str = "activity_log_v2"  # type: ignore[misc]
