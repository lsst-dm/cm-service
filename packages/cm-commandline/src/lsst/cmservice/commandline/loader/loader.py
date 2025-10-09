from pathlib import Path
from typing import Any

import typer
import yaml
from httpx import Headers, HTTPStatusError

from ..client import http_client


def yaml_to_json(yaml_docs: str) -> Any:
    """Converts a set of yaml documents to a JSON list."""
    _yamls = yaml.safe_load_all(yaml_docs)
    yield from _yamls


def load_selected_file(ctx: typer.Context, yaml_file: Path, campaign_name: str | None) -> Headers | None:
    """Load a collection of Manifests from a YAML file.

    If `campaign_name` is None, the campaign name must be set in the YAML file.

    Otherwise, the specified `campaign_name` will override whatever is in the
    YAML.
    """
    yaml_string = yaml_file.read_text()
    headers: Headers | None = None
    with http_client(ctx) as session:
        for yaml in yaml_to_json(yaml_string):
            capture_headers = False
            match yaml["kind"]:
                case "campaign":
                    uri = "/campaigns"
                    yaml["metadata"]["name"] = campaign_name or yaml["metadata"]["name"]
                    capture_headers = True
                case "node":
                    uri = "/nodes"
                    yaml["metadata"]["namespace"] = campaign_name or yaml["metadata"]["namespace"]
                case "edge":
                    uri = "/edges"
                    yaml["metadata"]["namespace"] = campaign_name or yaml["metadata"]["namespace"]
                case _:
                    uri = "/manifests"
                    yaml["metadata"]["namespace"] = campaign_name or yaml["metadata"]["namespace"]

            try:
                r = session.post(uri, json=yaml)
                r.raise_for_status()
                if capture_headers:
                    headers = r.headers
            except HTTPStatusError:
                print(f"Failed to create manifests: {r.text}")
                print(r.headers)
                break

    return headers
