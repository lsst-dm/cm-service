#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click==8.1.*",
#     "json-schema-for-humans>=1.5.1",
#     "lsst-cm-service",
#     "lsst-utils",
#     "pydantic==2.12.*",
# ]
#
# [tool.uv.sources]
# lsst-cm-service = { path = "../" }
# ///
"""Loads the CM Service Manifest Models and generates JSONSchema files"""

import json
import shutil
from pathlib import Path

import click
from json_schema_for_humans.generate import generate_from_file_object
from json_schema_for_humans.generation_configuration import GenerationConfiguration
from pydantic import BaseModel

from lsst.cmservice.models.manifests import bps, butler, facility, lsst, steps, wms

GENCONFIG = GenerationConfiguration(
    template_name="js_offline",
    show_breadcrumbs=False,
    examples_as_yaml=True,
    collapse_long_descriptions=False,
    link_to_reused_ref=True,
    description_is_markdown=True,
    with_footer=False,
)

MDCONFIG = GenerationConfiguration(
    template_name="md",
    show_breadcrumbs=False,
    collapse_long_descriptions=False,
    link_to_reused_ref=True,
    description_is_markdown=True,
)

STATIC_DIR = Path(__file__).parent.parent / "packages/cm-web/src/lsst/cmservice/web/static/docs"


@click.command()
@click.option("--html", is_flag=True, help="Output HTML")
@click.option("--markdown", is_flag=True, help="Output Markdown")
@click.option("--jsonschema", is_flag=True, default=True, help="Output JSON Schema")
@click.option("--clean/--no-clean", default=False, help="Empty target directory first")
@click.option(
    "--output",
    default=STATIC_DIR,
    help="Output directory",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
)
def main(*, html: bool, markdown: bool, jsonschema: bool, clean: bool, output: Path) -> None:
    if clean and output.exists():
        shutil.rmtree(output)

    output.mkdir(parents=False, exist_ok=True)

    manifest: BaseModel
    for manifest in [
        bps.BpsSpec,
        butler.ButlerSpec,
        facility.FacilitySpec,
        lsst.LsstSpec,
        steps.BreakpointSpec,
        steps.StepSpec,
        wms.WmsSpec,
    ]:
        manifest_schema = manifest.model_json_schema()
        manifest_title = manifest_schema["title"]

        if jsonschema:
            schema_file = output / f"{manifest_title}.jsonschema"
            schema_file.write_text(json.dumps(manifest_schema, indent=2))

        if html:
            human_file = schema_file.with_suffix(".html")
            with schema_file.open("r") as in_, human_file.open("w") as out_:
                generate_from_file_object(in_, out_, config=GENCONFIG)

        if markdown:
            markdown_file = schema_file.with_suffix(".md")
            with schema_file.open("r") as in_, markdown_file.open("w") as out_:
                generate_from_file_object(in_, out_, config=MDCONFIG)


if __name__ == "__main__":
    main()
