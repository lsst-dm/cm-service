"""create notification trigger

Revision ID: ec9e474c5388
Revises: 47243ea2b1bb
Create Date: 2026-07-17 14:33:39.728937+00:00

"""

from collections.abc import Sequence

from alembic import op
from lsst.cmservice.models.db import Base, raw

# revision identifiers, used by Alembic.
revision: str = "ec9e474c5388"
down_revision: str | None = "47243ea2b1bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(raw.NOTIFICATION_FUNCTION.format(schema=Base.metadata.schema))
    op.execute(raw.NOTIFICATION_TRIGGER.format(schema=Base.metadata.schema))


def downgrade() -> None:
    op.execute("""DROP TRIGGER IF EXISTS notification_events_trigger ON activity_log_v2;""")
    op.execute("""DROP FUNCTION IF EXISTS notify_event_listeners();""")
