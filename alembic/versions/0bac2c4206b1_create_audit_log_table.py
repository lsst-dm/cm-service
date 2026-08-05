"""create audit log table

Revision ID: 0bac2c4206b1
Revises: c8b0cbdc11b5
Create Date: 2026-07-06 14:24:23.030755+00:00

"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0bac2c4206b1"
down_revision: str | None = "c8b0cbdc11b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# DB model uses mapped columns with Python Enum types, but we do not care
# to use native enums in the database, so when we have such a column, this
# definition will produce a VARCHAR instead.
ENUM_COLUMN_AS_VARCHAR = sa.Enum(Enum, length=20, native_enum=False, check_constraint=False)


def upgrade() -> None:
    op.create_table(
        "audit_log_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("actor", postgresql.TEXT(), nullable=False),
        sa.Column("action", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column("object_id", postgresql.UUID(), nullable=False),
        sa.Column("object_type", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column("object_name", postgresql.TEXT(), nullable=False),
        sa.Column("request_id", postgresql.UUID(), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )

    op.execute("""
        CREATE INDEX ix_audit_log_context
        ON audit_log_v2
        USING gin (context jsonb_path_ops)
    """)


def downgrade() -> None:
    op.drop_index("ix_audit_log_context", table_name="audit_log_v2", if_exists=True)
    op.drop_table("audit_log_v2", if_exists=True)
