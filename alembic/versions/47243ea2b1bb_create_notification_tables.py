"""create notification tables

Revision ID: 47243ea2b1bb
Revises: 0bac2c4206b1
Create Date: 2026-07-17 14:33:15.521982+00:00

"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableList

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "47243ea2b1bb"
down_revision: str | None = "0bac2c4206b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# DB model uses mapped columns with Python Enum types, but we do not care
# to use native enums in the database, so when we have such a column, this
# definition will produce a VARCHAR instead.
ENUM_COLUMN_AS_VARCHAR = sa.Enum(Enum, length=20, native_enum=False, check_constraint=False)


def upgrade() -> None:

    op.create_table(
        "notification_labels_v2",
        sa.Column("name", postgresql.TEXT(), nullable=False),
        sa.Column("kind", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column("secret", postgresql.BYTEA(), nullable=True),
        sa.Column(
            "configuration",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("name"),
    )

    op.add_column(
        table_name="activity_log_v2",
        column=sa.Column(
            "notification_labels",
            MutableList.as_mutable(postgresql.ARRAY(postgresql.TEXT)),
            nullable=False,
            default=list,
            server_default=sa.text("'{}'::text[]"),
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_column(table_name="activity_log_v2", column_name="notification_labels", if_exists=True)
    op.drop_table("notification_labels_v2", if_exists=True)
