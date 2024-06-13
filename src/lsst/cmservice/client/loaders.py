from __future__ import annotations

import os
import yaml

from typing import Any, TYPE_CHECKING
from collections.abc import Mapping

import httpx

from ..common.errors import CMYamlParseError
from .. import models
from . import wrappers

if TYPE_CHECKING:
    from .client import CMClient
    from pydantic import BaseModel


def update_include_dict(
    orig_dict: dict[str, Any],
    include_dict: dict[str, Any],
) -> None:
    """Update a dict by updating (instead of replacing) sub-dicts

    Parameters
    ----------
    orig_dict: dict[str, Any]
        Original dict
    include_dict: dict[str, Any],
        Dict used to update the original
    """
    for key, val in include_dict.items():
        if isinstance(val, Mapping) and key in orig_dict:
            orig_dict[key].update(val)
        else:
            orig_dict[key] = val


class CMLoadClient:
    """Interface for accessing remote cm-service."""

    def __init__(self, parent: CMClient) -> None:
        """Return the httpx.Client"""
        self._parent = parent
        self._client = parent.client

    @property
    def client(self) -> httpx.Client:
        """Return the httpx.Client"""
        return self._client

    def _upsert_spec_block(
        self,
        config_values: dict,
        loaded_specs: dict,
        *,
        allow_update: bool = False,
    ) -> models.SpecBlock | None:
        """Upsert and return a SpecBlock

        This will create a new SpecBlock, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the SpecBlock

        loaded_specs: dict
            Already loaded SpecBlocks, used for include statments

        allow_update: bool
             Allow updating existing blocks

        Returns
        -------
        spec_block: SpecBlock
            Newly created or updated SpecBlock
        """
        key = config_values.pop("name")
        loaded_specs[key] = config_values

        spec_block = self._parent.spec_block.get_row_by_name(key)
        if spec_block and not allow_update:
            print(f"SpecBlock {key} already defined, skipping it")
            return None
        includes = config_values.pop("includes", [])
        block_data = config_values.copy()
        include_data: dict[str, Any] = {}
        for include_ in includes:
            if include_ in loaded_specs:
                update_include_dict(include_data, loaded_specs[include_])
            else:
                spec_block_ = self._parent.spec_block.get_row_by_name(include_)
                update_include_dict(
                    include_data,
                    {
                        "handler": spec_block_.handler,
                        "data": spec_block_.data,
                        "collections": spec_block_.collections,
                        "child_config": spec_block_.child_config,
                        "spec_aliases": spec_block_.spec_aliases,
                        "scripts": spec_block_.scripts,
                        "steps": spec_block_.steps,
                    },
                )

        for include_key, include_val in include_data.items():
            if include_key in block_data and isinstance(include_val, Mapping):
                block_data[include_key].update(include_val)
            else:
                block_data[include_key] = include_val

        handler = block_data.pop("handler", None)
        if spec_block is None:
            return self._parent.spec_block.create(
                name=key,
                handler=handler,
                data=block_data.get("data"),
                collections=block_data.get("collections"),
                child_config=block_data.get("child_config"),
                scripts=block_data.get("scripts"),
                steps=block_data.get("steps"),
            )

        return self._parent.spec_block.update(
            row_id=spec_block.id,
            name=key,
            handler=handler,
            data=block_data.get("data"),
            collections=block_data.get("collections"),
            child_config=block_data.get("child_config"),
            scripts=block_data.get("scripts"),
            steps=block_data.get("steps"),
        )

    def _upsert_script_template(
        self,
        config_values: dict,
        *,
        allow_update: bool = False,
    ) -> models.ScriptTemplate | None:
        """Upsert and return a ScriptTemplate

        This will create a new ScriptTemplate, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the ScriptTemplate

        allow_update: bool
            Allow updating existing templates

        Returns
        -------
        script_template: ScriptTemplate
            Newly created or updated ScriptTemplate
        """
        key = config_values.pop("name")
        script_template = self._parent.script_template.get_row_by_name(key)
        if script_template and not allow_update:
            print(f"ScriptTemplate {key} already defined, skipping it")
            return None

        file_path = config_values["file_path"]
        full_file_path = os.path.abspath(os.path.expandvars(file_path))
        with open(full_file_path, encoding="utf-8") as fin:
            data = yaml.safe_load(fin)

        if script_template is None:
            return self._parent.script_template.create(
                name=key,
                data=data,
            )

        return self._parent.script_template.update(
            row_id=script_template.id,
            name=key,
            data=data,
        )

    def _upsert_specification(
        self,
        config_values: dict,
        *,
        allow_update: bool = False,
    ) -> dict:
        """Upsert and return a Specification

        This will create a new Specification, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the ScriptTemplate

        allow_update: bool
            Allow updating existing templates

        Returns
        -------
        out_dict: dict
            The updated and loaded objects
        """
        out_dict: dict[str, list[BaseModel]] = dict(
            Specification=[],
            SpecBlockAssocication=[],
            ScriptTemplateAssociation=[],
        )

        spec_name = config_values["name"]
        script_templates = config_values.get("script_templates", [])
        spec_blocks = config_values.get("spec_blocks", [])

        specification = self._parent.specification.get_row_by_name(spec_name)
        new_spec = False
        if specification is None:
            specification = self._parent.specification.create(name=spec_name)

        for script_list_item_ in script_templates:
            try:
                script_template_config_ = script_list_item_["ScriptTemplateAssociation"]
            except KeyError as msg:
                raise CMYamlParseError(
                    f"Expected ScriptTemplateAssociation not {list(script_list_item_.keys())}",
                ) from msg

            script_template_name = script_template_config_["script_template_name"]
            alias = script_template_config_.get("alias", script_template_name)

            fullname = f"{spec_name}#{alias}"
            script_template_assoc = self._parent.script_template_association.get_row_by_fullname(
                fullname=fullname,
            )
            if script_template_assoc and not allow_update:
                print(f"ScriptTemplateAssociation {fullname} already defined, skipping it")
                continue

            if script_template_assoc is None:
                script_template_assoc = self._parent.script_template_association.create(
                    spec_name=spec_name,
                    **script_template_config_,
                )
                out_dict["ScriptTemplateAssociation"].append(script_template_assoc)
                continue

            # FIXME
            # I was too lazy to redo the association stuff for the update case
            # mostly b/c we should probably just ditch the whole
            # SpecBlockAssociation and ScriptTemplateAssociation thing. It is
            # doing the same thing as the spec_aliases and that fits better
            # into how we do everything else.
            #
            # script_template_assoc =
            # self._parent.script_template_association.update(
            #    row_id=script_template_assoc.id,
            #    spec_name=spec_name,
            #    **script_template_config_,
            # )

        for spec_block_list_item_ in spec_blocks:
            try:
                spec_block_config_ = spec_block_list_item_["SpecBlockAssociation"]
            except KeyError as msg:
                raise CMYamlParseError(
                    f"Expected SpecBlockAssociation not {list(spec_block_list_item_.keys())}",
                ) from msg

            spec_block_name = spec_block_config_["spec_block_name"]
            alias = spec_block_config_.get("alias", spec_block_name)
            fullname = f"{spec_name}#{alias}"

            spec_block_assoc = self._parent.spec_block_association.get_row_by_fullname(fullname=fullname)
            if spec_block_assoc and not allow_update:
                print(f"ScriptTemplateAssociation {fullname} already defined, skipping it")
                continue

            if spec_block_assoc is None:
                spec_block_assoc = self._parent.spec_block_association.create(
                    spec_name=spec_name,
                    **spec_block_config_,
                )
                out_dict["SpecBlockAssocication"].append(spec_block_assoc)
                continue

            # FIXME
            # I was too lazy to redo the association stuff for the update case
            # mostly b/c we should probably just ditch the whole
            # SpecBlockAssociation and ScriptTemplateAssociation thing. It is
            # doing the same thing as the spec_aliases and that fits better
            # into how we do everything else.
            #
            # spec_block_assoc = self._parent.spec_block_association.update(
            #    row_id=spec_block_assoc.id,
            #    spec_name=spec_name,
            #    **spec_block_config_,
            # )

        if new_spec or allow_update:
            out_dict["Specification"].append(specification)

        return out_dict

    def specification_cl(
        self,
        yaml_file: str,
        loaded_specs: dict | None = None,
        *,
        allow_update: bool = False,
    ) -> dict:
        """Read a yaml file and create Specification objects

        Parameters
        ----------
        yaml_file: str
            File in question

        loaded_specs: dict
            Already loaded SpecBlocks, used for include statments

        allow_update: bool
            Allow updating existing items

        Returns
        -------
        out_dict: dict
            The updated and loaded objects
        """
        if loaded_specs is None:
            loaded_specs = {}

        with open(yaml_file, encoding="utf-8") as fin:
            spec_data = yaml.safe_load(fin)

        out_dict: dict[str, list[BaseModel]] = dict(
            Specification=[],
            SpecBlockAssocication=[],
            ScriptTemplateAssociation=[],
            SpecBlock=[],
            ScriptTemplate=[],
        )

        for config_item in spec_data:
            if "Imports" in config_item:
                imports = config_item["Imports"]
                for import_ in imports:
                    imported_ = self.specification_cl(
                        os.path.abspath(os.path.expandvars(import_)),
                        loaded_specs,
                        allow_update=allow_update,
                    )
                    for key, val in imported_.items():
                        out_dict[key] += val
            elif "SpecBlock" in config_item:
                spec_block = self._upsert_spec_block(
                    config_item["SpecBlock"],
                    loaded_specs,
                    allow_update=allow_update,
                )
                if spec_block:
                    out_dict["SpecBlock"].append(spec_block)
            elif "ScriptTemplate" in config_item:
                script_template = self._upsert_script_template(
                    config_item["ScriptTemplate"],
                    allow_update=allow_update,
                )
                if script_template:
                    out_dict["ScriptTemplate"].append(script_template)
            elif "Specification" in config_item:
                extra_dict = self._upsert_specification(
                    config_item["Specification"],
                    allow_update=allow_update,
                )
                for key, val in extra_dict.items():
                    out_dict[key] += val
            else:
                good_keys = "ScriptTemplate | SpecBlock | Specification | Imports"
                raise CMYamlParseError(f"Expecting one of {good_keys} not: {spec_data.keys()})")

        return out_dict

    specification = wrappers.get_general_post_function(
        models.SpecificationLoad,
        models.Specification,
        "load/specification",
    )

    campaign = wrappers.get_general_post_function(
        models.LoadAndCreateCampaign,
        models.Campaign,
        "load/campaign",
    )

    error_types = wrappers.get_general_post_function(
        models.YamlFileQuery,
        list[models.PipetaskErrorType],
        "load/error_types",
    )

    manifest_report = wrappers.get_general_post_function(
        models.LoadManifestReport,
        models.Job,
        "load/manifest_report",
    )
