from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import httpx
import yaml

from .. import models
from ..common.enums import ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from ..common.errors import CMYamlParseError
from ..common.logging import LOGGER
from ..common.utils import update_include_dict
from . import wrappers

if TYPE_CHECKING:
    from pydantic import BaseModel

    from .client import CMClient


logger = LOGGER.bind(module=__name__)


class CMLoadClient:
    """Interface for accessing remote cm-service."""

    production = "DEFAULT"
    namespace = ""

    def __init__(self, parent: CMClient) -> None:
        """Return the httpx.Client"""
        self._parent = parent
        self._client = parent.client

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
    ) -> models.SpecBlock:
        """Upsert and return a SpecBlock

        This will create a new SpecBlock, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the SpecBlock

        loaded_specs: dict
            Already loaded SpecBlocks, used for include statments

        allow_update: bool

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
            else:  # pragma: no cover
                # This is just in case the spec blocks are defined
                # out of order in the specification file
                spec_block_ = self._parent.spec_block.get_row_by_name(include_)
                update_include_dict(
                    include_data,
                    {
                        "handler": spec_block_.handler,
                        "data": spec_block_.data or {},
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

    def _upsert_specification(
        self,
        config_values: dict,
        *,
        allow_update: bool = False,
    ) -> models.Specification:
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
            Allow updating existing items (DEPRECATED: always False)

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
        )

        for config_item in spec_data:
            if "Imports" in config_item:
                imports = config_item["Imports"]
                # Recursive specification loading from indicated Import files
                for import_ in imports:
                    # Do not reimport seed files, they are "protected"
                    if "seed" in import_:
                        continue
                    imported_ = self.specification_cl(
                        os.path.abspath(os.path.expandvars(import_)),
                        loaded_specs,
                        allow_update=allow_update,
                    )
                    for key, val in imported_.items():
                        out_dict[key] += val
            elif "Manifest" in config_item:
                # bridge from a Manifest to a legacy SpecBlock. This code path
                # explicitly does not support "update" operations on global or
                # shared specblocks.
                try:
                    manifest = config_item["Manifest"]
                    spec_block = manifest["spec"]
                    # update the name of the spec with the campaign namespace
                    spec_block["name"] = ".".join([self.namespace, manifest["metadata"]["name"]])
                    spec_block = self._upsert_spec_block(
                        spec_block,
                        loaded_specs,
                        allow_update=False,
                    )
                    out_dict["SpecBlock"].append(spec_block)
                except Exception:
                    logger.exception()
            elif "SpecBlock" in config_item:
                spec_block = config_item["SpecBlock"]
                spec_block["name"] = ".".join([self.namespace, spec_block["name"]])
                spec_block = self._upsert_spec_block(
                    spec_block,
                    loaded_specs,
                    allow_update=allow_update,
                )
                out_dict["SpecBlock"].append(spec_block)
            elif "Specification" in config_item:
                specification = self._upsert_specification(
                    config_item["Specification"],
                    allow_update=allow_update,
                )
                out_dict["Specification"].append(specification)
            else:  # pragma: no cover
                good_keys = "Manifest | SpecBlock | Specification | Imports"
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
    ) -> models.Campaign:
        """Read a yaml file and create campaign

        Parameters
        ----------
        campaign_yaml: str
            Yaml file with campaign overrides (a "start" file)

        yaml_file: str
            Optional yaml file with specifications (an "example" file)

        Returns
        -------
        campaign : `Campaign`
            Newly created `Campaign`
        """
        with open(campaign_yaml, encoding="utf-8") as fin:
            config_data = yaml.safe_load(fin)

        try:
            parent_name = self.production
            campaign_config = config_data["Campaign"]
            campaign_config["parent_name"] = parent_name
            self.namespace = campaign_config["name"]
        except KeyError as msg:
            raise CMYamlParseError(
                f"Could not find 'Campaign' tag in {campaign_yaml}",
            ) from msg

        if TYPE_CHECKING:
            assert isinstance(campaign_config, dict)

        for key in ["data", "child_config", "collections", "spec_aliases"]:
            campaign_config.setdefault(key, {})
            # if key not in campaign_config:
            #     campaign_config[key] = {}

        # The spec_name is the by-name reference to an existing campaign
        # specification that should already be seeded in the database.
        spec_name = campaign_config["spec_name"]

        if yaml_file is None:  # pragma: no cover
            # If yaml_file isn't given then the specifications
            # should already exist
            specification = self._parent.specification.get_row_by_name(spec_name)
            if specification is None:
                raise CMYamlParseError(
                    f"Could not find 'Specification' {spec_name} in {campaign_yaml}",
                )
        else:
            self.specification_cl(yaml_file, allow_update=False)

        spec_name = campaign_config["spec_name"]
        campaign_config["spec_block_assoc_name"] = f"{spec_name}#campaign"

        step_configs = campaign_config.pop("steps", [])
        campaign = self._parent.campaign.create(**campaign_config)

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
    ) -> models.PipetaskErrorType:
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
        task_name = config_values["task_name"].strip()
        diag_message = config_values["diagnostic_message"].strip()
        fullname = f"{task_name}#{diag_message}"
        error_type = self._parent.pipetask_error_type.get_row_by_fullname(fullname)
        if error_type is None:
            return self._parent.pipetask_error_type.create(**config_values)

        if not allow_update:
            return error_type

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

            val["error_source"] = ErrorSourceEnum[val["error_source"]]
            val["error_action"] = ErrorActionEnum[val["error_action"]]
            val["error_flavor"] = ErrorFlavorEnum[val["error_flavor"]]

            new_error_type = self._upsert_error_type(val, allow_update=allow_update)
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
