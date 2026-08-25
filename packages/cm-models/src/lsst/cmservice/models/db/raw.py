"""Module maintaining raw SQL objects, especially functions, triggers, etc."""

from textwrap import dedent

NOTIFICATION_TRIGGER = dedent("""\
    CREATE TRIGGER notification_events_trigger
    AFTER INSERT ON {schema}.activity_log_v2
    FOR EACH ROW
    EXECUTE FUNCTION {schema}.notify_event_listeners();
""")
"""SQL trigger to call a function when new rows are inserted to the activity
log table.
"""


NOTIFICATION_FUNCTION = dedent("""\
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
"""SQL function to generate PG_NOTIFY messages when called from an insert
trigger on the activity log table.
"""
