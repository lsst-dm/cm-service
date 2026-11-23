"""Formatter functions for campaign commands in the CM Service CLI"""

from collections.abc import Mapping, Sequence
from datetime import datetime

from rich.table import Table

CONTEXT_VALUE_MAX_LENGTH = 40
"""Maximum display length of a single audit context value in a table cell."""

HIDDEN_CONTEXT_KEYS = {"namespace"}
"""Audit context keys omitted from table output, i.e., because the campaign
is already the subject of the table.
"""


def format_audit_context(context: Mapping) -> str:
    """Render an audit log context mapping as compact `key=value` lines,
    truncating long values.
    """
    lines = []
    for k, v in context.items():
        if k in HIDDEN_CONTEXT_KEYS:
            continue
        value = str(v)
        if len(value) > CONTEXT_VALUE_MAX_LENGTH:
            value = f"{value[: CONTEXT_VALUE_MAX_LENGTH - 1]}…"
        lines.append(f"{k}={value}")
    return "\n".join(lines)


def format_audit_time(created_at: str) -> str:
    """Render an audit log ISO8601 timestamp to whole seconds."""
    try:
        return datetime.fromisoformat(created_at).isoformat(timespec="seconds")
    except ValueError:
        return created_at


def as_audit_table(o: Sequence[Mapping], *, title: str, caption: str | None = None) -> Table:
    """Render a sequence of audit log entries as a table."""
    table = Table(title=title, caption=caption)
    table.add_column("Time")
    table.add_column("Actor")
    table.add_column("Action")
    table.add_column("Kind")
    table.add_column("Object")
    table.add_column("Context")

    for row in o:
        table.add_row(
            format_audit_time(row["created_at"]),
            row["actor"],
            row["action"],
            row["object_type"],
            row["object_name"],
            format_audit_context(row.get("context") or {}),
        )
    return table
