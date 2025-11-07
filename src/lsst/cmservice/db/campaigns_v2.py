"""ORM Models for v2 tables and objects."""

from collections.abc import MutableSequence
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from pydantic import AliasChoices, AwareDatetime, ValidationInfo, model_validator
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.types import PickleType
from sqlmodel import Column, DateTime, Enum, Field, MetaData, Relationship, SQLModel, String

from ..common.enums import ManifestKind, StatusEnum
from ..common.timestamp import now_utc
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


class BaseSQLModel(AsyncAttrs, SQLModel):
    """Shared base SQL model for all tables."""

    __table_args__ = {"schema": config.db.table_schema}
    metadata = metadata


class CampaignBase(BaseSQLModel):
    """Campaigns_v2 base model, used to create new Campaign objects."""

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID
    owner: str | None = Field(default=None)
    status: StatusField = Field(
        default=StatusEnum.waiting,
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])
    machine: UUID | None = Field(foreign_key="machines_v2.id", default=None, ondelete="CASCADE")

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        """Validates the model based on different types of raw inputs,
        where some default non-optional fields can be auto-populated.
        """
        if isinstance(data, dict):
            if "name" not in data:
                raise ValueError("<campaign> name missing.")
            if "namespace" not in data:
                data["namespace"] = _default_campaign_namespace
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=data["name"])
        return data


class Campaign(CampaignBase, table=True):
    """Model used for database operations involving campaigns_v2 table rows"""

    __tablename__: str = "campaigns_v2"  # type: ignore[misc]

    nodes: list["Node"] = Relationship(back_populates="campaign")


class CampaignUpdate(BaseSQLModel):
    """Model representing updatable fields for a PATCH operation on a Campaign
    using RFC7396.
    """

    owner: str | None = None
    status: StatusField | None = None
    force: bool = Field(default=False, description="Makes the status change unconditional.")


class CampaignSummary(CampaignBase):
    """Model for the response of a Campaign Summary route."""

    node_summary: MutableSequence["NodeStatusSummary"] = Field(default_factory=list)


class NodeStatusSummary(BaseSQLModel):
    """Model for a Node Status Summary."""

    status: StatusField = Field(description="A state name")
    count: int = Field(description="Count of nodes in this state")
    mtime: AwareDatetime | None = Field(description="The most recent update time for nodes in this state")


class NodeBase(BaseSQLModel):
    """nodes_v2 db table"""

    def __hash__(self) -> int:
        """A Node is hashable according to its unique ID, so it can be used in
        sets and other places hashable types are required.
        """
        return self.id.int  # pyright: ignore[reportReturnType]

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    version: int
    kind: KindField = Field(
        default=ManifestKind.other,
        sa_column=Column("kind", Enum(ManifestKind, length=20, native_enum=False, create_constraint=False)),
    )
    status: StatusField = Field(
        default=StatusEnum.waiting,
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])
    machine: UUID | None = Field(foreign_key="machines_v2.id", default=None, ondelete="CASCADE")

    @model_validator(mode="before")
    @classmethod
    def custom_model_validator(cls, data: Any, info: ValidationInfo) -> Any:
        """Validates the model based on different types of raw inputs,
        where some default non-optional fields can be auto-populated.
        """
        if isinstance(data, dict):
            if (node_name := data.get("name")) is None:
                raise ValueError("<node> name missing.")
            if (node_namespace := data.get("namespace")) is None:
                raise ValueError("<node> namespace missing.")
            if (node_version := data.get("version")) is None:
                data["version"] = node_version = 1
            if "id" not in data:
                data["id"] = uuid5(namespace=node_namespace, name=f"{node_name}.{node_version}")
        return data


class Node(NodeBase, table=True):
    __tablename__: str = "nodes_v2"  # type: ignore[misc]

    campaign: Campaign = Relationship(
        back_populates="nodes",
        sa_relationship_kwargs={"lazy": "joined", "innerjoin": True, "uselist": False},
    )

    fsm: "Machine" = Relationship(sa_relationship_kwargs={"uselist": False})


class EdgeBase(BaseSQLModel):
    """edges_v2 db table"""

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    source: UUID = Field(foreign_key="nodes_v2.id")
    target: UUID = Field(foreign_key="nodes_v2.id")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    configuration: dict = jsonb_column("configuration", aliases=["configuration", "data", "spec"])


class EdgeResponseModel(EdgeBase):
    source: Any
    target: Any


class Edge(EdgeBase, table=True):
    __tablename__: str = "edges_v2"  # type: ignore[misc]


class MachineBase(BaseSQLModel):
    """machines_v2 db table."""

    id: UUID = Field(primary_key=True, default_factory=uuid4)
    state: Any = Field(sa_column=Column("state", PickleType))


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


class Manifest(ManifestBase, table=True):
    __tablename__: str = "manifests_v2"  # type: ignore[misc]


class Task(BaseSQLModel, table=True):
    """tasks_v2 db table"""

    __tablename__: str = "tasks_v2"  # type: ignore[misc]

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        description="A hash of the related Node ID and target status, as a UUID5.",
    )
    namespace: UUID = Field(foreign_key="campaigns_v2.id", description="The ID of a Campaign")
    node: UUID = Field(foreign_key="nodes_v2.id", description="The ID of the target node")
    priority: int | None = Field(default=None)
    created_at: AwareDatetime = Field(
        description="The `datetime` (UTC) at which this Task was first added to the queue",
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True)),
    )
    submitted_at: AwareDatetime | None = Field(
        description="The `datetime` (UTC) at which this Task was first submitted as work to the event loop",
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    finished_at: AwareDatetime | None = Field(
        description=(
            "The `datetime` (UTC) at which this Task successfully finalized. "
            "A Task whose `finished_at` is not `None` is tombstoned and is subject to deletion."
        ),
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    wms_id: str | None = Field(default=None)
    site_affinity: list[str] | None = Field(
        default=None, sa_column=Column("site_affinity", MutableList.as_mutable(postgresql.ARRAY(String())))
    )
    status: StatusField = Field(
        description="The 'target' status to which this Task will attempt to transition the Node",
        sa_column=Column("status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)),
    )
    previous_status: StatusField = Field(
        description="The 'original' status from which this Task will attempt to transition the Node",
        sa_column=Column(
            "previous_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])
    node_orm: Node = Relationship(sa_relationship_kwargs={"uselist": False})


class ActivityLogBase(BaseSQLModel):
    id: UUID = Field(primary_key=True, default_factory=uuid4)
    namespace: UUID = Field(foreign_key="campaigns_v2.id", description="The ID of a Campaign")
    node: UUID | None = Field(default=None, foreign_key="nodes_v2.id", description="The ID of a Node")
    operator: str = Field(description="The name of the operator or pilot who triggered the activity")
    created_at: AwareDatetime = Field(
        description="The `datetime` in UTC at which this log entry was created.",
        default_factory=now_utc,
        sa_column=Column(DateTime(timezone=True)),
    )
    finished_at: AwareDatetime | None = Field(
        description="The `datetime` in UTC at which this log entry was finalized.",
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    to_status: StatusField = Field(
        description=(
            "The `target` state to which this activity tried to transition. "
            "This may be the same as `from_status` in cases where no transition was attempted "
            "(such as for a conditional check)."
        ),
        sa_column=Column(
            "to_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    from_status: StatusField = Field(
        description="The `original` state from which this activity tried to transition",
        sa_column=Column(
            "from_status", Enum(StatusEnum, length=20, native_enum=False, create_constraint=False)
        ),
    )
    detail: dict = jsonb_column("detail")
    metadata_: dict = jsonb_column("metadata", aliases=["metadata", "metadata_"])


class ActivityLog(ActivityLogBase, table=True):
    __tablename__: str = "activity_log_v2"  # type: ignore[misc]
