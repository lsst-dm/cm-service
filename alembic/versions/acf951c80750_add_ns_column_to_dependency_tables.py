"""Add NS column to dependency tables

Revision ID: acf951c80750
Revises: 4c8e81aceea9
Create Date: 2025-06-02 19:34:07.552520+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "acf951c80750"
down_revision: str | None = "4c8e81aceea9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_TABLES = ["script_dependency", "step_dependency"]


def upgrade() -> None:
    for table in TARGET_TABLES:
        op.add_column(
            table_name=table,
            column=sa.Column(
                "namespace",
                UUID,
                nullable=True,
                default=None,
                server_default=None,
            ),
        )


def downgrade() -> None:
    for table in TARGET_TABLES:
        op.drop_column(
            table_name=table,
            column_name="namespace",
        )
