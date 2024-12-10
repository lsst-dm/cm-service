"""create Enums for v0.4.0

Revision ID: fc48b549d66f
Revises:
Create Date: 2024-12-10 20:46:41.666699+00:00

This migration was created by copying the set of Enum definitions from the
results of `alembic revision --autocreate` at tag release v0.4.0. These Enums
are created (or dropped) separately to the table DDL where they are used.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import MetaData

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fc48b549d66f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Create Enums used by CM Service
cm_enums = [
    sa.Enum("cmservice", "local_script", "manifest", name="errorsourceenum", metadata=MetaData()),
    sa.Enum("infrastructure", "configuration", "pipelines", name="errorflavorenum", metadata=MetaData()),
    sa.Enum(
        "fail",
        "requeue_and_pause",
        "rescue",
        "auto_retry",
        "review",
        "accept",
        name="erroractionenum",
        metadata=MetaData(),
    ),
    sa.Enum(
        "failed",
        "rejected",
        "paused",
        "rescuable",
        "waiting",
        "ready",
        "prepared",
        "running",
        "reviewable",
        "accepted",
        "rescued",
        name="statusenum",
        metadata=MetaData(),
    ),
    sa.Enum(
        "production",
        "campaign",
        "step",
        "group",
        "job",
        "script",
        "n_levels",
        name="levelenum",
        metadata=MetaData(),
    ),
    sa.Enum(
        "default",
        "no_script",
        "bash",
        "slurm",
        "htcondor",
        name="scriptmethodenum",
        metadata=MetaData(),
    ),
]


def upgrade() -> None:
    for e in cm_enums:
        e.create(op.get_bind())


def downgrade() -> None:
    for e in cm_enums:
        e.drop(op.get_bind())
