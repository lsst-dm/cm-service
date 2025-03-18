"""Load Seeds

Revision ID: 69b048e66619
Revises: fb13f1f4ea21
Create Date: 2025-03-17 21:14:53.876441+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import MetaData

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "69b048e66619"
down_revision: str | None = "fb13f1f4ea21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    meta = MetaData()
    # Insert default production record
    productions = sa.Table("production", meta, autoload_with=op.get_bind())

    op.bulk_insert(
        productions,
        [
            {
                "name": "DEFAULT",
            }
        ],
    )


def downgrade() -> None:
    pass
