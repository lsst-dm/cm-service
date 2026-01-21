import typer

from . import options
from .campaigns.app import app as campaigns_app
from .loader.app import app as loader_app
from .manifests.app import app as manifests_app
from .models import AppContext, TypedContext
from .nodes.app import app as nodes_app
from .settings import settings

app = typer.Typer()
app.add_typer(campaigns_app, name="campaigns")
app.add_typer(loader_app, name="load")
app.add_typer(manifests_app, name="manifests")
app.add_typer(nodes_app, name="nodes")


@app.callback()
def build_context(
    ctx: TypedContext,
    output: options.output = "table",
    endpoint: options.endpoint = settings.endpoint,
    token: options.token = settings.token,
) -> None:
    ctx.obj = AppContext(output_format=output, endpoint_url=endpoint, auth_token=token)


if __name__ == "__main__":
    app()
