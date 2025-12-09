"""create v2 tables

Revision ID: 1da92a1c740f
Revises: acf951c80750
Create Date: 2025-06-13 14:56:31.238050+00:00

"""

from collections.abc import Sequence
from enum import Enum
from uuid import NAMESPACE_DNS

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1da92a1c740f"
down_revision: str | None = "acf951c80750"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_CAMPAIGN_NAMESPACE = "dda54a0c-6878-5c95-ac4f-007f6808049e"
"""UUID5 of name 'io.lsst.cmservice' in `uuid.NAMESPACE_DNS`."""

# DB model uses mapped columns with Python Enum types, but we do not care
# to use native enums in the database, so when we have such a column, this
# definition will produce a VARCHAR instead.
ENUM_COLUMN_AS_VARCHAR = sa.Enum(Enum, length=20, native_enum=False, check_constraint=False)


def upgrade() -> None:
    # Create table for machines v2
    machines_v2 = op.create_table(
        "machines_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("state", sa.PickleType, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    # Create table for campaigns v2
    campaigns_v2 = op.create_table(
        "campaigns_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False, default=DEFAULT_CAMPAIGN_NAMESPACE),
        sa.Column("owner", postgresql.VARCHAR(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("status", ENUM_COLUMN_AS_VARCHAR, nullable=False, default="waiting"),
        sa.Column(
            "machine", postgresql.UUID(), sa.ForeignKey(machines_v2.c.id, ondelete="CASCADE"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "namespace"),
        if_not_exists=True,
    )

    # Create node and edges tables for campaign digraph
    nodes_v2 = op.create_table(
        "nodes_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column(
            "namespace",
            postgresql.UUID(),
            sa.ForeignKey(campaigns_v2.c.id, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("version", postgresql.INTEGER(), nullable=False, default=1),
        sa.Column("kind", ENUM_COLUMN_AS_VARCHAR, nullable=False, default="node"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column("status", ENUM_COLUMN_AS_VARCHAR, nullable=False, default="waiting"),
        sa.Column(
            "machine", postgresql.UUID(), sa.ForeignKey(machines_v2.c.id, ondelete="CASCADE"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", "namespace"),
        if_not_exists=True,
    )

    _ = op.create_table(
        "edges_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column(
            "namespace",
            postgresql.UUID(),
            sa.ForeignKey(campaigns_v2.c.id, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", postgresql.UUID(), sa.ForeignKey(nodes_v2.c.id), nullable=False),
        sa.Column("target", postgresql.UUID(), sa.ForeignKey(nodes_v2.c.id), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "target", "namespace"),
        if_not_exists=True,
    )

    # Create table for spec blocks v2 ("manifests")
    _ = op.create_table(
        "manifests_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column(
            "namespace",
            postgresql.UUID(),
            sa.ForeignKey(campaigns_v2.c.id, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", postgresql.INTEGER(), nullable=False, default=1),
        sa.Column("kind", ENUM_COLUMN_AS_VARCHAR, nullable=False, default="other"),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "spec",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "version", "namespace", name="manifests_v2_name_version_namespace_key"),
        if_not_exists=True,
    )

    # Create table for tasks v2
    _ = op.create_table(
        "tasks_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("node", postgresql.UUID(), nullable=False),
        sa.Column("priority", postgresql.INTEGER(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("submitted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("wms_id", postgresql.VARCHAR(), nullable=True),
        sa.Column("site_affinity", postgresql.ARRAY(postgresql.VARCHAR()), nullable=True),
        sa.Column("status", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column("previous_status", ENUM_COLUMN_AS_VARCHAR, nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["node"], ["nodes_v2.id"]),
        sa.ForeignKeyConstraint(["namespace"], ["campaigns_v2.id"]),
        if_not_exists=True,
    )

    _ = op.create_table(
        "activity_log_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("node", postgresql.UUID(), sa.ForeignKey(nodes_v2.c.id), nullable=True),
        sa.Column("operator", postgresql.VARCHAR(), nullable=False, default="root"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("from_status", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column("to_status", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column(
            "detail",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    # Insert default campaign (namespace) record
    op.bulk_insert(
        campaigns_v2,
        [
            {
                "id": DEFAULT_CAMPAIGN_NAMESPACE,
                "namespace": str(NAMESPACE_DNS),
                "name": "DEFAULT",
                "owner": "root",
            }
        ],
    )


def downgrade() -> None:
    """Drop tables in the reverse order in which they were created."""
    op.drop_table("activity_log_v2", if_exists=True)
    op.drop_table("tasks_v2", if_exists=True)
    op.drop_table("manifests_v2", if_exists=True)
    op.drop_table("edges_v2", if_exists=True)
    op.drop_table("nodes_v2", if_exists=True)
    op.drop_table("campaigns_v2", if_exists=True)
    op.drop_table("machines_v2", if_exists=True)
