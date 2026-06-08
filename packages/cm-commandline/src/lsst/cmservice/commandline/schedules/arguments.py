from typing import Annotated

import typer
from pydantic_extra_types.cron import CronStr


def parse_cron_str(value: str) -> CronStr:
    return CronStr(value)


cron = Annotated[CronStr, typer.Argument(help="A five-token cron expression string.", parser=parse_cron_str)]
