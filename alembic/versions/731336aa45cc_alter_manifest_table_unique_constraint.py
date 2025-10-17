"""Alter manifest table unique constraint

Revision ID: 731336aa45cc
Revises: 3cadff0118ab
Create Date: 2025-10-17 14:54:24.951931+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "731336aa45cc"
down_revision: str | None = "3cadff0118ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "manifests_v2_name_version_namespace_key",
        table_name="manifests_v2",
        type_="unique",
    )
    op.create_unique_constraint(
        constraint_name="manifests_v2_name_version_kind_namespace_key",
        table_name="manifests_v2",
        columns=["name", "version", "kind", "namespace"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "manifests_v2_name_version_kind_namespace_key",
        table_name="manifests_v2",
        type_="unique",
    )
    op.create_unique_constraint(
        constraint_name="manifests_v2_name_version_namespace_key",
        table_name="manifests_v2",
        columns=["name", "version", "namespace"],
    )
