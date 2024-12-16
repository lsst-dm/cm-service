"""Script template indices for v0.4.0

Revision ID: fb13f1f4ea21
Revises: cacc1bb4152e
Create Date: 2024-12-16 21:14:03.584656+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb13f1f4ea21"
down_revision: str | None = "cacc1bb4152e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_script_template_name"), "script_template", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_script_template_name"), table_name="script_template")
