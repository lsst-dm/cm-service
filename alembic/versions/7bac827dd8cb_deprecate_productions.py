"""Deprecate Productions

Revision ID: 7bac827dd8cb
Revises: cef0ebaa8241
Create Date: 2025-03-18 21:14:09.976660+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7bac827dd8cb"
down_revision: str | None = "cef0ebaa8241"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Remove production-related indexes
    op.drop_index(op.f("ix_campaign_parent_id"), table_name="campaign", if_exists=True)
    op.drop_index(op.f("ix_production_name"), table_name="production", if_exists=True)

    # Remove FK constraint and parent id column from campaigns table
    op.drop_constraint(constraint_name="campaign_parent_id_fkey", table_name="campaign", type_="foreignkey")
    op.drop_column(table_name="campaign", column_name="parent_id")

    # Drop the productions table
    op.drop_table("production", if_exists=True)


def downgrade() -> None: ...
