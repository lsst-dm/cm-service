"""create new campaign tables

Revision ID: 20e0532d3758
Revises: fb13f1f4ea21
Create Date: 2025-02-21 20:14:01.167798+00:00

"""

from collections.abc import Sequence
from uuid import NAMESPACE_DNS

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20e0532d3758"
down_revision: str | None = "fb13f1f4ea21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_CAMPAIGN_NAMESPACE = "dda54a0c-6878-5c95-ac4f-007f6808049e"
"""UUID5 of name 'io.lsst.cmservice' in `uuid.NAMESPACE_DNS`."""


def upgrade() -> None:
    # Create table for campaigns v2
    campaigns_v2 = op.create_table(
        "campaigns_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False, default=DEFAULT_CAMPAIGN_NAMESPACE),
        sa.Column("owner", postgresql.VARCHAR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("configuration", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "namespace"),
    )

    # Create node and edges tables for campaign digraph
    op.create_table(
        "nodes_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("version", postgresql.INTEGER(), nullable=False, default=1),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace"], ["campaigns_v2.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("name", "version", "namespace"),
    )

    # Do edges need names?
    op.create_table(
        "edges_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("source", postgresql.UUID(), nullable=False),
        sa.Column("target", postgresql.UUID(), nullable=False),
        sa.Column("configuration", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace"], ["campaigns_v2.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source"], ["nodes_v2.id"]),
        sa.ForeignKeyConstraint(["target"], ["nodes_v2.id"]),
        sa.UniqueConstraint("source", "target", "namespace"),
    )

    # Create table for spec blocks v2 ("manifests")
    op.create_table(
        "manifests_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.VARCHAR(), nullable=False),
        sa.Column("version", postgresql.INTEGER(), nullable=False, default=1),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("spec", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["namespace"], ["campaigns_v2.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("name", "version", "namespace"),
    )

    # Create table for tasks v2
    op.create_table(
        "tasks_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("namespace", postgresql.UUID(), nullable=False),
        sa.Column("node", postgresql.UUID(), nullable=False),
        sa.Column("priority", postgresql.INTEGER(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("last_processed_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(), nullable=True),
        sa.Column("wms_id", postgresql.VARCHAR(), nullable=True),
        sa.Column("site_affinity", postgresql.ARRAY(postgresql.VARCHAR()), nullable=True),
        sa.Column("status", postgresql.INTEGER(), nullable=True),
        sa.Column("previous_status", postgresql.INTEGER(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["node"], ["nodes_v2.id"]),
        sa.ForeignKeyConstraint(["namespace"], ["campaigns_v2.id"]),
    )

    # Insert default campaign (namespace) record
    # campaigns = sa.Table('campaigns_v2', meta, autoload_with=op.get_bind())

    op.bulk_insert(
        campaigns_v2,
        [
            {
                "id": DEFAULT_CAMPAIGN_NAMESPACE,
                "namespace": str(NAMESPACE_DNS),
                "name": "DEFAULT",
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("tasks_v2")
    op.drop_table("manifests_v2")
    op.drop_table("edges_v2")
    op.drop_table("nodes_v2")
    op.drop_table("campaigns_v2")
