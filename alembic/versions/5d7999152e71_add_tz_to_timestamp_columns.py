"""Add TZ to TIMESTAMP columns

Revision ID: 5d7999152e71
Revises: abde345860c5
Create Date: 2025-05-29 19:14:49.555637+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d7999152e71"
down_revision: str | None = "abde345860c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_COLUMNS = ["time_created", "time_updated", "time_finished", "time_next_check"]


def upgrade() -> None:
    for column in TARGET_COLUMNS:
        op.alter_column(
            table_name="queue",
            column_name=column,
            type_=TIMESTAMP(timezone=True),
        )


def downgrade() -> None:
    for column in TARGET_COLUMNS:
        op.alter_column(
            table_name="queue",
            column_name=column,
            type_=sa.DateTime,
        )
