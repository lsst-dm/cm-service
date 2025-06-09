"""Add active and metadata columns to queue

Revision ID: 4c8e81aceea9
Revises: 5d7999152e71
Create Date: 2025-05-30 15:07:07.388833+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4c8e81aceea9"
down_revision: str | None = "5d7999152e71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("queue") as batch_op:
        batch_op.add_column(
            column=sa.Column(
                "metadata_",
                MutableDict.as_mutable(JSONB),
                nullable=False,
                default=dict,
                server_default=sa.text("'{}'::json"),
            ),
        )
        batch_op.add_column(
            column=sa.Column(
                "active",
                sa.Boolean,
                nullable=False,
                default=False,
                server_default=sa.sql.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("queue") as batch_op:
        batch_op.drop_column(
            column_name="metadata_",
        )
        batch_op.drop_column(
            column_name="active",
        )
