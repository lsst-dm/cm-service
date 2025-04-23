"""Error indices for v0.4.0

Revision ID: cacc1bb4152e
Revises: 92053b1ad093
Create Date: 2024-12-16 21:10:24.132473+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cacc1bb4152e"
down_revision: str | None = "92053b1ad093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_pipetask_error_error_type_id"), "pipetask_error", ["error_type_id"], unique=False
    )
    op.create_index(op.f("ix_pipetask_error_task_id"), "pipetask_error", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pipetask_error_task_id"), table_name="pipetask_error", if_exists=True)
    op.drop_index(op.f("ix_pipetask_error_error_type_id"), table_name="pipetask_error", if_exists=True)
