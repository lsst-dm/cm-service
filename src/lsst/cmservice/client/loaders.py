from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import httpx
import yaml

from .. import models
from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from ..common.errors import CMYamlParseError
from . import wrappers

if TYPE_CHECKING:
    from pydantic import BaseModel

    from .client import CMClient


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

    groups = wrappers.get_general_post_function(models.AddGroups, list[models.Group], "load/groups")

    steps = wrappers.get_general_post_function(models.AddSteps, models.Campaign, "load/steps")

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
            return spec_block
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

        block_data = include_data.copy()
        update_include_dict(block_data, config_values.copy())

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
            return script_template

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
    ) -> models.Specification | None:
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
        spec_name = config_values["name"]

        specification = self._parent.specification.get_row_by_name(spec_name)
        if specification is not None and not allow_update:
            return specification

        if specification is None:
            specification = self._parent.specification.create(**config_values)
            return specification

        return self._parent.specification.update(
            row_id=specification.id,
            **config_values,
        )

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
                specification = self._upsert_specification(
                    config_item["Specification"],
                    allow_update=allow_update,
                )
                if specification:
                    out_dict["Specification"].append(specification)
            else:
                good_keys = "ScriptTemplate | SpecBlock | Specification | Imports"
                raise CMYamlParseError(f"Expecting one of {good_keys} not: {spec_data.keys()})")

        return out_dict

    specification = wrappers.get_general_post_function(
        models.SpecificationLoad,
        models.Specification,
        "load/specification",
    )

    def campaign_cl(
        self,
        campaign_yaml: str,
        yaml_file: str | None = None,
        *,
        allow_update: bool = False,
        **kwargs: Any,
    ) -> models.Campaign:
        """Read a yaml file and create campaign

        Parameters
        ----------
        campaign_yaml: str
            Yaml file with campaign overrides

        yaml_file: str
            Optional yaml file with specifications

        allow_update: bool
            Allow updating existing specification items

        Note
        ----
        The keywords optionally override values from the config_file

        Keywords
        --------
        name: str | None
            Name for the campaign

        parent_name: str | None
            Name for the production

        spec_name: str | None
            Name of the specification to use

        handler: str | None
            Name of the callback Handler to use

        data: dict | None
            Overrides for the campaign data parameter dict

        child_config: dict | None
            Overrides for the campaign child_config dict

        collections: dict | None
            Overrides for the campaign collection dict

        spec_aliases: dict | None
            Overrides for the campaign spec_aliases dict

        Returns
        -------
        campaign : `Campaign`
            Newly created `Campaign`
        """
        if yaml_file is not None:
            self.specification_cl(yaml_file, allow_update=allow_update)

        with open(campaign_yaml, encoding="utf-8") as fin:
            config_data = yaml.safe_load(fin)

        try:
            prod_config = config_data["Production"]
        except KeyError as msg:
            raise CMYamlParseError(
                f"Could not find 'Production' tag in {campaign_yaml}",
            ) from msg
        try:
            parent_name = prod_config["name"]
        except KeyError as msg:
            raise CMYamlParseError(
                f"Could not find 'name' tag in {campaign_yaml}#Production",
            ) from msg

        try:
            camp_config = config_data["Campaign"]
            camp_config["parent_name"] = parent_name
        except KeyError as msg:
            raise CMYamlParseError(
                f"Could not find 'Campaign' tag in {campaign_yaml}",
            ) from msg

        assert isinstance(camp_config, dict)

        # flush out config_data with kwarg overrides
        for key in ["name", "parent_name", "spec_name", "handler"]:
            val = kwargs.get(key, None)
            if val:
                camp_config[key] = val

        for key in ["data", "child_config", "collections", "spec_aliases"]:
            camp_config.setdefault(key, {})
            val = kwargs.get(key, None)
            if val:
                update_include_dict(camp_config[key], val)

        production = self._parent.production.get_row_by_name(parent_name)
        if not production:
            self._parent.production.create(name=parent_name)

        spec_name = camp_config["spec_name"]
        camp_config["spec_block_assoc_name"] = f"{spec_name}#campaign"

        step_configs = camp_config.pop("steps", [])
        campaign = self._parent.campaign.create(**camp_config)

        if step_configs:
            self.steps(fullname=campaign.fullname, child_configs=step_configs)

        return campaign

    campaign = wrappers.get_general_post_function(
        models.LoadAndCreateCampaign,
        models.Campaign,
        "load/campaign",
    )

    def _upsert_error_type(
        self,
        config_values: dict,
        *,
        allow_update: bool = False,
    ) -> models.PipetaskErrorType | None:
        """Upsert and return a PipetaskErrorType

        This will create a new PipetaskErrorType, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the PipetaskErrorType

        allow_update: bool
             Allow updating existing PipetaskErrorType

        Returns
        -------
        error_type: PipetaskErrorType
            Newly created or updated PipetaskErrorType
        """
        task_name = config_values["task_name"]
        diag_message = config_values["diagnostic_message"]
        fullname = f"{task_name}#{diag_message}".strip()
        error_type = self._parent.pipetask_error_type.get_row_by_fullname(fullname)
        if error_type and not allow_update:
            return error_type

        if error_type is None:
            return self._parent.pipetask_error_type.create(**config_values)

        return self._parent.pipetask_error_type.update(
            row_id=error_type.id,
            **config_values,
        )

    def error_types_cl(
        self,
        yaml_file: str,
        *,
        allow_update: bool = False,
    ) -> list[models.PipetaskErrorType]:
        """Read a yaml file and create PipetaskErrorType objects

        Parameters
        ----------
        yaml_file: str
            Optional yaml file with PipetaskErrorType definitinos

        allow_update: bool
            Allow updating existing PipetaskErrorType items

        Returns
        -------
        error_types: list[models.PipetaskErrorType]
            Newly created or updated PipetaskErrorType objects
        """
        with open(yaml_file, encoding="utf-8") as fin:
            error_types = yaml.safe_load(fin)

        ret_list: list[models.PipetaskErrorType] = []
        for error_type_ in error_types:
            try:
                val = error_type_["PipetaskErrorType"]
            except KeyError as msg:
                raise CMYamlParseError(
                    f"Expecting PipetaskErrorType items not: {error_type_.keys()})",
                ) from msg

            val["error_source"] = ErrorSourceEnum[val["source"]]
            val["error_action"] = ErrorActionEnum[val["action"]]
            val["error_flavor"] = ErrorFlavorEnum[val["flavor"]]

            new_error_type = self._upsert_error_type(val, allow_update=allow_update)
            if new_error_type:
                ret_list.append(new_error_type)

        return ret_list

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
