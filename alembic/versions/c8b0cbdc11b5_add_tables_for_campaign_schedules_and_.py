"""Add tables for campaign schedules and templates

Revision ID: c8b0cbdc11b5
Revises: 731336aa45cc
Create Date: 2026-03-27 15:11:33.227603+00:00

"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8b0cbdc11b5"
down_revision: str | None = "731336aa45cc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# DB model uses mapped columns with Python Enum types, but we do not care
# to use native enums in the database, so when we have such a column, this
# definition will produce a VARCHAR instead.
ENUM_COLUMN_AS_VARCHAR = sa.Enum(Enum, length=20, native_enum=False, check_constraint=False)


def upgrade() -> None:
    op.create_table(
        "schedules_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("name", postgresql.TEXT(), nullable=False),
        sa.Column("cron", postgresql.TEXT(), nullable=False),
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
        sa.Column("is_enabled", postgresql.BOOLEAN(), default=False, nullable=False),
        sa.Column("next_run_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_schedule_name"),
        if_not_exists=True,
    )

    op.create_table(
        "templates_v2",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(), nullable=False),
        sa.Column("version", postgresql.INTEGER(), nullable=False, default=1),
        sa.Column("name", postgresql.TEXT(), nullable=False),
        sa.Column("kind", ENUM_COLUMN_AS_VARCHAR, nullable=False),
        sa.Column(
            "manifest",
            postgresql.TEXT(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            default=dict,
            server_default=sa.text("'{}'::json"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules_v2.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("schedule_id", "kind", "name", "version", name="uq_schedule_name_kind_version"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("templates_v2", if_exists=True)
    op.drop_table("schedules_v2", if_exists=True)
