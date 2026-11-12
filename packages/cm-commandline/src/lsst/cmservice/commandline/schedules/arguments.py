from typing import Annotated

import typer
from pydantic_extra_types.cron import CronStr


def parse_cron_str(value: str) -> CronStr:
    return CronStr(value)


cron = Annotated[CronStr, typer.Argument(help="A five-token cron expression string.", parser=parse_cron_str)]


def validate_expressions(value: list[str] | None) -> list[str] | None:
    """Validates that each override expressions option is a NAME=VALUE pair."""
    for expression in value or []:
        name, _, rhs = expression.partition("=")
        if not name.strip() or not rhs.strip():
            msg = f"Expected NAME=EXPRESSION, got {expression!r}"
            raise typer.BadParameter(msg)
    return value


def parse_expressions(value: list[str] | None) -> dict[str, str]:
    """Parses a list of NAME=VALUE pairs as a mapping."""
    return {name.strip(): rhs.strip() for name, _, rhs in (e.partition("=") for e in value or [])}


expressions = Annotated[
    list[str] | None,
    typer.Option(
        "--expression",
        "-e",
        help=(
            "A NAME=EXPRESSION pair overriding or adding a template value for this oneshot only. "
            "May be repeated."
        ),
        callback=validate_expressions,
    ),
]

idempotency_key = Annotated[
    str | None,
    typer.Option(help="A key identifying this oneshot; reusing a key does not create a new campaign."),
]
