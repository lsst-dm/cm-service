"""Deprecate ScriptTemplates

Revision ID: cef0ebaa8241
Revises: fb13f1f4ea21
Create Date: 2025-03-18 20:22:38.960167+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cef0ebaa8241"
down_revision: str | None = "fb13f1f4ea21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_script_template_name"), table_name="script_template", if_exists=True)
    op.drop_table("script_template", if_exists=True)


def downgrade() -> None:
    # There is no going back.
    pass
