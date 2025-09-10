from typing import Annotated

import typer

output = Annotated[str, typer.Option(help="Output format table|json", envvar="CM_OUTPUT_FORMAT")]

endpoint = Annotated[str, typer.Option(help="CM Service Endpoint URL", envvar="CM_ENDPOINT")]

token = Annotated[str, typer.Option(help="Gafaelfawr Access Token", envvar="CM_TOKEN", hidden=True)]
