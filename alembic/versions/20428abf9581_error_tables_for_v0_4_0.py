"""Error tables for v0.4.0

Revision ID: 20428abf9581
Revises: f5e50e000a35
Create Date: 2024-12-13 22:07:55.828266+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import MetaData

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20428abf9581"
down_revision: str | None = "f5e50e000a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create table for Pipetask Error Types
    op.create_table(
        "pipetask_error_type",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "error_source",
            sa.Enum(
                "cmservice",
                "local_script",
                "manifest",
                name="errorsourceenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column(
            "error_flavor",
            sa.Enum(
                "infrastructure",
                "configuration",
                "pipelines",
                name="errorflavorenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
        sa.Column(
            "error_action",
            sa.Enum(
                "fail",
                "requeue_and_pause",
                "rescue",
                "auto_retry",
                "review",
                "accept",
                name="erroractionenum",
                create_type=False,
                metadata=MetaData(),
            ),
            nullable=False,
        ),
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
    op.drop_table("pipetask_error")
    op.drop_table("pipetask_error_type")
