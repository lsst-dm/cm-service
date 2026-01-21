from pathlib import Path
from typing import Any

import typer
import yaml
from httpx import Headers, HTTPStatusError

from ..client import http_client
from ..models import TypedContext


class StrictModeViolationError(RuntimeError): ...


def yaml_to_json(yaml_docs: str, *, strict: bool = False) -> Any:
    """Converts a set of yaml documents to a JSON list."""
    _yamls = yaml.safe_load_all(yaml_docs)
    if strict:
        # for strict mode, we sacrifice efficiency for correctness
        # TODO we could partition the manifests by kind, then yield them in a
        # particular order (e.g., campaigns, manifests, nodes, edges)
        found_one_campaign = False
        strict_yamls: list[Any] = []
        for _yaml in _yamls:
            if _yaml["kind"] == "campaign" and not found_one_campaign:
                strict_yamls.insert(0, _yaml)
                found_one_campaign = True
            elif _yaml["kind"] == "campaign" and found_one_campaign:
                raise StrictModeViolationError("A YAML file may have only a single Campaign manifest")
            else:
                strict_yamls.append(_yaml)
        if not found_one_campaign:
            raise StrictModeViolationError("A YAML file must have exactly one Campaign manifest")
        yield from strict_yamls
    else:
        yield from _yamls


def load_selected_file(
    ctx: TypedContext, *, yaml_file: Path, campaign: str | None, strict: bool = False
) -> Headers | None:
    """Load a collection of Manifests from a YAML file.

    If `campaign` is None, the campaign name must be set for each manifest in
    the YAML file.

    Otherwise, the specified `campaign_name` will override whatever is in the
    YAML.

    In `strict` mode, a YAML file may have exactly one campaign manifest,
    `campaign` must be set, and the campaign manifest is loaded first. Any
    violation of strict mode raises a `StrictModeViolationError`.
    """
    yaml_string = yaml_file.read_text()
    headers: Headers | None = None

    with http_client(ctx) as session:
        for yaml in yaml_to_json(yaml_string, strict=strict):
            capture_headers = False
            match yaml["kind"]:
                case "campaign":
                    uri = "/campaigns"
                    yaml["metadata"]["name"] = yaml["metadata"]["name"] if campaign is None else campaign
                    capture_headers = True
                case "node":
                    uri = "/nodes"
                    yaml["metadata"]["namespace"] = (
                        yaml["metadata"]["namespace"] if campaign is None else ctx.obj.campaign_id
                    )
                case "edge":
                    uri = "/edges"
                    yaml["metadata"]["namespace"] = (
                        yaml["metadata"]["namespace"] if campaign is None else ctx.obj.campaign_id
                    )
                case _:
                    uri = "/manifests"
                    yaml["metadata"]["namespace"] = (
                        yaml["metadata"]["namespace"] if campaign is None else ctx.obj.campaign_id
                    )

            try:
                r = session.post(uri, json=yaml)
                r.raise_for_status()
                if capture_headers:
                    headers = r.headers
            except HTTPStatusError:
                typer.echo(f"Failed to create manifests: {r.text}", err=True)
                raise typer.Exit(1)

    return headers
