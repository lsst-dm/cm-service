"""create notification trigger

Revision ID: ec9e474c5388
Revises: 47243ea2b1bb
Create Date: 2026-07-17 14:33:39.728937+00:00

"""

from collections.abc import Sequence
from textwrap import dedent

from alembic import op
from lsst.cmservice.models.db import Base

# revision identifiers, used by Alembic.
revision: str = "ec9e474c5388"
down_revision: str | None = "47243ea2b1bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NOTIFICATION_FUNCTION = dedent("""\
    -- function to notify listeners based on the content of the label array for new notifications
    CREATE OR REPLACE FUNCTION {schema}.notify_event_listeners()
    RETURNS TRIGGER AS $$
    DECLARE
        label_name TEXT;
        label_kind TEXT;
        payload TEXT;
    BEGIN
        FOREACH label_name in ARRAY NEW.notification_labels
        LOOP
            label_kind := NULL;
            payload := json_build_object(
                'id', NEW.id::text,
                'label', label_name
            );
            SELECT kind INTO label_kind FROM {schema}.notification_labels_v2 WHERE name = label_name;
            PERFORM pg_notify(COALESCE(label_kind, 'default'), payload::text);
        END LOOP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
""")

NOTIFICATION_TRIGGER = dedent("""\
    -- trigger for INSERTs
    CREATE TRIGGER notification_events_trigger
    AFTER INSERT ON {schema}.activity_log_v2
    FOR EACH ROW
    EXECUTE FUNCTION {schema}.notify_event_listeners();
""")


def upgrade() -> None:
    op.execute(NOTIFICATION_FUNCTION.format(schema=Base.metadata.schema))
    op.execute(NOTIFICATION_TRIGGER.format(schema=Base.metadata.schema))


def downgrade() -> None:
    op.execute("""DROP TRIGGER IF EXISTS notification_events_trigger ON activity_log_v2;""")
    op.execute("""DROP FUNCTION IF EXISTS notify_event_listeners();""")
