"""add metadata column to campaign elements

Revision ID: 0b064a0096bf
Revises: 7bac827dd8cb
Create Date: 2025-05-21 15:30:03.144451+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0b064a0096bf"
down_revision: str | None = "7bac827dd8cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_TABLES = ["campaign", "step", "group", "job", "script"]


def upgrade() -> None:
    for table in TARGET_TABLES:
        op.add_column(
            table_name=table,
            column=sa.Column(
                "metadata_",
                MutableDict.as_mutable(JSONB),
                nullable=False,
                default=dict,
            ),
            # if_not_exists=True,  # TODO alembic>1.16
        )


def downgrade() -> None:
    for table in TARGET_TABLES:
        op.drop_column(
            table_name=table,
            column_name="metadata_",
            # if_exists=True,  # TODO alembic>1.16
        )
