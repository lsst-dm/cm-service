import typer

from . import options
from .campaigns.app import app as campaigns_app
from .loader.app import app as loader_app
from .manifests.app import app as manifests_app
from .settings import settings

app = typer.Typer()
app.add_typer(campaigns_app, name="campaigns")
app.add_typer(loader_app, name="load")
app.add_typer(manifests_app, name="manifests")


@app.callback()
def build_context(
    ctx: typer.Context,
    output: options.output = "table",
    endpoint: options.endpoint = settings.endpoint,
    token: options.token = settings.token,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["output_format"] = output
    ctx.obj["cm_endpoint_url"] = endpoint


if __name__ == "__main__":
    app()
