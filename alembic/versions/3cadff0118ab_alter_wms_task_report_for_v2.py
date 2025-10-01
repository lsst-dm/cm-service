"""alter wms_task_report for v2

Revision ID: 3cadff0118ab
Revises: 1da92a1c740f
Create Date: 2025-10-01 14:48:22.609772+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3cadff0118ab"
down_revision: str | None = "1da92a1c740f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_TABLES = ["wms_task_report"]


def upgrade() -> None:
    # Modify the wms_task_set table for v2 by adding an optional pair of UUID
    # columns for v2 namespace and node IDs.
    for table in TARGET_TABLES:
        op.add_column(
            table_name=table,
            column=sa.Column(
                "namespace",
                postgresql.UUID(),
                nullable=True,
                default=None,
            ),
            if_not_exists=True,
        )

        op.add_column(
            table_name=table,
            column=sa.Column(
                "node",
                postgresql.UUID(),
                nullable=True,
                default=None,
            ),
            if_not_exists=True,
        )


def downgrade() -> None:
    for table in TARGET_TABLES:
        op.drop_column(
            table_name=table,
            column_name="node",
            if_exists=True,
        )
        op.drop_column(
            table_name=table,
            column_name="namespace",
            if_exists=True,
        )
