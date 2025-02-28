from datetime import datetime
from typing import Any
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import ValidationInfo, model_validator
from sqlalchemy.dialects import postgresql
from sqlmodel import Column, Field, SQLModel, String

_default_campaign_namespace = uuid5(namespace=NAMESPACE_DNS, name="io.lsst.cmservice")
"""Default UUID5 namespace for campaigns"""


# NOTES
# - model validation is not triggered when table=True
# - Every object model needs to have three flavors:
#   1. the declarative model of the object's database table
#   2. the model of the manifest when creating a new object
#   3. a response model for APIs related to the object


class CampaignBase(SQLModel):
    """campaigns_v2 db table"""

    __tablename__: str = "campaigns_v2"

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID
    owner: str | None = Field(default=None)
    metadata_: dict = Field(
        sa_type=postgresql.JSONB, default_factory=dict, sa_column_kwargs={"name": "metadata"}
    )
    configuration: dict = Field(sa_type=postgresql.JSONB, default_factory=dict)


class CampaignModel(CampaignBase):
    """model used for resource creation."""

    @model_validator(mode="before")
    @classmethod
    def generate_id(cls, data: Any, info: ValidationInfo) -> Any:
        # this feels wrong, mutating the input dictionary? Maybe not.
        # assume raw input is a dict or can be duck-typed as one
        if isinstance(data, dict):
            if "name" not in data:
                raise ValueError("'name' must be specified.")
            if "namespace" not in data:
                data["namespace"] = _default_campaign_namespace
            if "id" not in data:
                data["id"] = uuid5(namespace=data["namespace"], name=data["name"])
        return data


class Campaign(CampaignModel, table=True): ...


class NodeBase(SQLModel):
    """nodes_v2 db table"""

    __tablename__: str = "nodes_v2"

    id: UUID = Field(primary_key=True)
    name: str
    version: int
    namespace: UUID
    configuration: dict = Field(sa_type=postgresql.JSONB, default_factory=dict)


class NodeModel(NodeBase):
    """model validating class for Nodes"""

    @model_validator(mode="before")
    @classmethod
    def generate_id(cls, data: Any, info: ValidationInfo) -> Any:
        # if hasattr(data, "_mapping"):
        #     return data._mapping["Node"]
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


class Node(NodeModel, table=True): ...


class EdgeBase(SQLModel):
    """edges_v2 db table"""

    __tablename__: str = "edges_v2"

    id: UUID = Field(primary_key=True)
    name: str
    namespace: UUID = Field(foreign_key="campaigns_v2.id")
    source: UUID = Field(foreign_key="nodes_v2.id")
    target: UUID = Field(foreign_key="nodes_v2.id")
    configuration: dict = Field(sa_type=postgresql.JSONB, default_factory=dict)


class EdgeModel(EdgeBase):
    """model validating class for Edges"""

    @model_validator(mode="before")
    @classmethod
    def generate_id(cls, data: Any, info: ValidationInfo) -> Any:
        # if hasattr(data, "_mapping"):
        #     try:
        #         return data._mapping["Edge"]
        #     except KeyError:
        #         return data._mapping
        if isinstance(data, dict):
            # if "version" not in data:
            #     data["version"] = 1
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


class Edge(EdgeModel, table=True): ...


class ManifestBase(SQLModel):
    """manifests_v2 db table"""

    __tablename__: str = "manifests_v2"

    id: UUID = Field(primary_key=True)
    name: str
    version: int
    namespace: UUID
    metadata_: dict = Field(
        sa_type=postgresql.JSONB, default_factory=dict, sa_column_kwargs={"name": "metadata"}
    )
    spec: dict = Field(sa_type=postgresql.JSONB, default_factory=dict)


class ManifestModel(ManifestBase):
    """model validating class for Manifests"""

    @model_validator(mode="before")
    @classmethod
    def generate_id(cls, data: Any, info: ValidationInfo) -> Any:
        # if hasattr(data, "_mapping"):
        #     return data._mapping["Manifest"]
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


class Manifest(ManifestBase, table=True): ...


class Task(SQLModel, table=True):
    """tasks_v2 db table"""

    __tablename__: str = "tasks_v2"

    id: UUID = Field(primary_key=True)
    namespace: UUID
    node: UUID
    priority: int
    created_at: datetime
    last_processed_at: datetime
    finished_at: datetime
    wms_id: str
    site_affinity: list[str] = Field(sa_column=Column(postgresql.ARRAY(String())))
    status: int
    previous_status: int
