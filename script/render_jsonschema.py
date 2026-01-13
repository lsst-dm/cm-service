"""Loads the CM Service Manifest Models and generates JSONSchema files"""

import json
from pathlib import Path

from json_schema_for_humans.generate import generate_from_file_object
from json_schema_for_humans.generation_configuration import GenerationConfiguration

from lsst.cmservice.models.manifests import bps, butler, facility, lsst, steps, wms

GENCONFIG = GenerationConfiguration(
    template_name="js_offline",
    show_breadcrumbs=True,
    collapse_long_descriptions=False,
    link_to_reused_ref=True,
    description_is_markdown=True,
)

MDCONFIG = GenerationConfiguration(
    template_name="md",
    show_breadcrumbs=True,
    collapse_long_descriptions=False,
    link_to_reused_ref=True,
    description_is_markdown=True,
)

STATIC_DIR = Path("packages/cm-web/src/lsst/cmservice/web/static/docs")


def main():
    for manifest in [
        bps.BpsSpec,
        butler.ButlerSpec,
        facility.FacilitySpec,
        lsst.LsstSpec,
        steps.StepSpec,
        wms.WmsSpec,
    ]:
        STATIC_DIR.mkdir(parents=False, exist_ok=True)
        manifest_schema = manifest.model_json_schema()
        manifest_title = manifest_schema["title"]
        schema_file = STATIC_DIR / f"{manifest_title}.jsonschema"
        human_file = schema_file.with_suffix(".html")
        markdown_file = schema_file.with_suffix(".md")
        schema_file.write_text(json.dumps(manifest_schema, indent=2))

        with schema_file.open("r") as in_, human_file.open("w") as out_:
            generate_from_file_object(in_, out_, config=GENCONFIG)

        with schema_file.open("r") as in_, markdown_file.open("w") as out_:
            generate_from_file_object(in_, out_, config=MDCONFIG)


if __name__ == "__main__":
    main()
