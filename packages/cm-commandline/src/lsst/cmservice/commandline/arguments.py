from typing import Annotated

import typer

campaign_name = Annotated[str, typer.Argument(envvar="CM_CAMPAIGN")]

campaign_id = Annotated[str, typer.Argument()]
