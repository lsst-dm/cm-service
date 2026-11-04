"""drop legacy tables

Revision ID: 8217594f8818
Revises: 13b66c87f62a
Create Date: 2026-11-04 14:47:59.635577+00:00

Drops the legacy (v1) tables that are no longer part of the ORM model. Indexes,
constraints, and the serial id sequences owned by these tables are dropped with
them. This migration is destructive and cannot be downgraded.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8217594f8818"
down_revision: str | None = "13b66c87f62a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Legacy tables in foreign-key dependency order, i.e., each table is listed
# before any table it references.
LEGACY_TABLES = [
    "queue",
    "script_dependency",
    "script_error",
    "pipetask_error",
    "product_set",
    "wms_task_report",
    "step_dependency",
    "script",
    "task_set",
    "pipetask_error_type",
    "job",
    "group",
    "step",
    "campaign",
    "spec_block",
    "specification",
]


def upgrade() -> None:
    for table in LEGACY_TABLES:
        op.drop_table(table, if_exists=True)


def downgrade() -> None: ...
