"""Alter campaign element data columns

Revision ID: abde345860c5
Revises: 0b064a0096bf
Create Date: 2025-05-21 19:53:00.104217+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "abde345860c5"
down_revision: str | None = "0b064a0096bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_TABLES = ["campaign", "step", "group", "job", "script"]


def upgrade() -> None:
    for table in TARGET_TABLES:
        op.alter_column(
            table_name=table,
            column_name="data",
            nullable=False,
            server_default=sa.text("'{}'::json"),
        )


def downgrade() -> None:
    for table in TARGET_TABLES:
        op.alter_column(
            table_name=table,
            column_name="data",
            nullable=True,
            server_default=None,
        )
