"""Tests for the cli application's http client"""

from pathlib import Path
from textwrap import dedent

import pytest
import respx
import typer
from httpx2 import codes
from typer.testing import CliRunner

from lsst.cmservice.commandline.cli import app as cm_app
from lsst.cmservice.commandline.client import http_client
from lsst.cmservice.commandline.models import AppContext, TypedContext

ENDPOINT = "http://cm.example.com/cm/api"

app = typer.Typer()


@app.callback()
def build_context(ctx: TypedContext) -> None:
    ctx.obj = AppContext(output_format="json", endpoint_url=ENDPOINT)


@app.command()
def run(ctx: TypedContext, error: str = "none") -> None:
    """A command that raises the requested error in the client context."""
    with http_client(ctx) as client:
        match error:
            case "exit":
                raise typer.Exit(3)
            case "abort":
                raise typer.Abort()
            case "usage":
                raise typer.BadParameter("bad parameter")
            case "error":
                raise ValueError("unexpected error")
            case "http":
                client.get("/resource").raise_for_status()
    typer.echo("after the client context")


@pytest.mark.parametrize(
    "error,exit_code",
    [("exit", 3), ("abort", 1), ("usage", 2), ("error", 1), ("http", 1)],
)
def test_client_errors_end_the_command(
    httpx2_mock: respx.Router, runner: CliRunner, error: str, exit_code: int
) -> None:
    """Tests that an error in the client context ends the command with a
    failure exit code, instead of letting the command continue.
    """
    if error == "http":
        httpx2_mock.get(f"{ENDPOINT}/v2/resource").respond(codes.NOT_FOUND)
    result = runner.invoke(app, ["run", "--error", error])
    assert result.exit_code == exit_code
    assert "after the client context" not in result.output


def test_client_success(runner: CliRunner) -> None:
    """Tests that a command continues after a client context without error."""
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "after the client context" in result.output


def test_load_failure_exit_code(httpx2_mock: respx.Router, runner: CliRunner, tmp_path: Path) -> None:
    """Tests that a failure to load a manifest ends the cm command with a
    failure exit code.
    """
    manifest = tmp_path / "manifests.yaml"
    manifest.write_text(
        dedent("""\
            apiVersion: io.lsst.cmservice/v1
            kind: notification_label
            metadata:
              name: label
            spec: {}
        """)
    )
    httpx2_mock.post(f"{ENDPOINT}/v2/notifications/").respond(codes.NOT_FOUND, json={"detail": "Not Found"})
    result = runner.invoke(cm_app, ["--endpoint", ENDPOINT, "load", "yaml", str(manifest)])
    assert result.exit_code == 1
