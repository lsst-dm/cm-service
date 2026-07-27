"""alter_manifest_default

Revision ID: 13b66c87f62a
Revises: ec9e474c5388
Create Date: 2026-07-27 15:17:35.693736+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "13b66c87f62a"
down_revision: str | None = "ec9e474c5388"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        table_name="manifests_v2",
        column=sa.Column(
            "default",
            sa.BOOLEAN,
            nullable=False,
            server_default=sa.false(),
        ),
        if_not_exists=True,
    )

    op.create_index(
        index_name="ix_manifest_single_default",
        table_name="manifests_v2",
        columns=["namespace", "kind"],
        unique=True,
        postgresql_where=sa.text('"default" IS TRUE'),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_manifest_single_default", table="manifests_v2", if_exists=True)
    op.drop_column("manifests_v2", "default", if_exists=True)
