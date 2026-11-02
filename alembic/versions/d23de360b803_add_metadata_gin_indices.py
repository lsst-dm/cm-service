"""add metadata gin indices

Revision ID: d23de360b803
Revises: 8217594f8818
Create Date: 2026-11-02 21:05:15.382803+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d23de360b803"
down_revision: str | None = "8217594f8818"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


METADATA_GIN_INDICES = {
    "ix_campaigns_v2_metadata_gin": "campaigns_v2",
    "ix_nodes_v2_metadata_gin": "nodes_v2",
}


def upgrade() -> None:
    for index_name, table_name in METADATA_GIN_INDICES.items():
        op.create_index(
            index_name=index_name,
            table_name=table_name,
            columns=["metadata"],
            postgresql_using="gin",
            postgresql_ops={"metadata": "jsonb_path_ops"},
            if_not_exists=True,
        )


def downgrade() -> None:
    for index_name, table_name in METADATA_GIN_INDICES.items():
        op.drop_index(index_name=index_name, table_name=table_name, if_exists=True)
