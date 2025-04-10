"""Error tables for v0.4.0

Revision ID: 20428abf9581
Revises: f5e50e000a35
Create Date: 2024-12-13 22:07:55.828266+00:00

"""

from collections.abc import Sequence
from enum import Enum

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20428abf9581"
down_revision: str | None = "f5e50e000a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # DB model uses mapped columns with Python Enum types, but we do not care
    # to use native enums in the database, so when we have such a column, this
    # defintion will produce a VARCHAR instead.
    enum_column_as_varchar = sa.Enum(Enum, native_enum=False, check_constraint=False)

    # Create table for Pipetask Error Types
    op.create_table(
        "pipetask_error_type",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("error_source", enum_column_as_varchar, nullable=False),
        sa.Column("error_flavor", enum_column_as_varchar, nullable=False),
        sa.Column("error_action", enum_column_as_varchar, nullable=False),
        sa.Column("task_name", sa.String(), nullable=False),
        sa.Column("diagnostic_message", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_name", "diagnostic_message"),
    )
    # Create table for Pipetask Errors
    op.create_table(
        "pipetask_error",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("error_type_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("quanta", sa.String(), nullable=False),
        sa.Column("diagnostic_message", sa.String(), nullable=False),
        sa.Column("data_id", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["error_type_id"], ["pipetask_error_type.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["task_set.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quanta"),
    )


def downgrade() -> None:
    op.drop_table("pipetask_error", if_exists=True)
    op.drop_table("pipetask_error_type", if_exists=True)
