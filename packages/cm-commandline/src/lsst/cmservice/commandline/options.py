from typing import Annotated

import typer

output = Annotated[str, typer.Option(help="Output format table|json", envvar="CM_OUTPUT_FORMAT")]

endpoint = Annotated[str, typer.Option(help="CM Service Endpoint URL", envvar="CM_ENDPOINT")]

token = Annotated[str, typer.Option(help="Gafaelfawr Access Token", envvar="CM_TOKEN", hidden=True)]

limit = Annotated[
    int,
    typer.Option(min=1, max=100, help="Maximum number of elements to fetch per request"),
]

user = Annotated[str | None, typer.Option(help="Username of the request actor", envvar="CM_USER")]
