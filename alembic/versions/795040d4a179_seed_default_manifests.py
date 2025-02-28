"""seed default manifests

Revision ID: 795040d4a179
Revises: 20e0532d3758
Create Date: 2025-02-26 16:18:21.121414+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "795040d4a179"
down_revision: str | None = "20e0532d3758"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    meta = sa.MetaData()
    _ = sa.Table("campaigns_v2", meta, autoload_with=op.get_bind())
    _ = sa.Table("manifests_v2", meta, autoload_with=op.get_bind())

    # load seed file (YAML) and translate to db rows
    ...


def downgrade() -> None:
    pass
