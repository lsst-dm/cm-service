from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

import httpx
import yaml
from pydantic.v1.utils import deep_update

from .. import models
from ..common.enums import DEFAULT_NAMESPACE, ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from ..common.errors import CMYamlParseError
from ..common.logging import LOGGER
from . import wrappers

if TYPE_CHECKING:
    from pydantic import BaseModel

    from .client import CMClient


logger = LOGGER.bind(module=__name__)


class CMLoadClient:
    """Interface for accessing remote cm-service."""

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
        spec: dict,
        loaded_specs: dict,
        *,
        allow_update: bool = False,
        namespace: UUID,
    ) -> models.SpecBlock:
        """Upsert and return a SpecBlock

        This will create a new SpecBlock, or update an existing one

        Parameters
        ----------
        spec: dict
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
        spec_name: str = spec.pop("name")
        key = str(uuid5(namespace, spec_name))

        # the spec is added to the loaded_specs object, keyed by its uuid,
        # which is the short name of the spec block within the campaign name-
        # space
        loaded_specs[key] = spec

        spec_block = self._parent.spec_block.get_row_by_name(key)
        if spec_block and not allow_update:
            return spec_block

        logger.info(f"Loading spec_block {spec_name} as {key}")

        # A spec that "includes" another spec is effectively declaring a clone
        # of the referenced spec that should have already been "loaded" such
        # that we can dereference it from the loaded_specs mapping

        # the list of spec names to "include"
        includes = spec.pop("includes", [])

        # the new spec as a shallow copy of its input
        block_data = spec.copy()

        # a mapping to contain any/all "included" spec data
        include_data: dict[str, Any] = {}
        for include_ in includes:
            namespaced_spec = str(uuid5(namespace, include_))

            # The case where the include pointer has already been encount-
            # ered by the loader and can be referenced directly by name or a
            # namespaced uuid
            if namespaced_spec in loaded_specs:
                include_data = deep_update(include_data, loaded_specs[namespaced_spec])
            elif include_ in loaded_specs:
                include_data = deep_update(include_data, loaded_specs[include_])
            # The case where the spec blocks are defined out of order in
            # the specification file and it is not yet part of the loaded
            # specs mapping.
            else:  # pragma: no cover
                # FIXME why are we going to the database for this? Won't this
                #       be a None if there's no such record?
                if (spec_block_ := self._parent.spec_block.get_row_by_name(namespaced_spec)) is None:
                    spec_block_ = self._parent.spec_block.get_row_by_name(include_)

                if spec_block is None:
                    logger.error(f"Specified spec block {include_} cannot be found")
                    sys.exit(1)

                include_data = deep_update(
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

        block_data = deep_update(include_data, spec)

        # the block data deep references to other spec_blocks by name need to
        # be updated with namespaced names in child_config, scripts, & steps
        if "child_config" in block_data:
            block_data["child_config"] = deep_update(
                block_data["child_config"],
                {
                    k: str(uuid5(namespace, v))
                    for k, v in block_data["child_config"].items()
                    if k == "spec_block"
                },
            )

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
        namespace: UUID,
        allow_update: bool = False,
    ) -> models.Specification:
        """Upsert and return a Specification

        This will create a new Specification, or update an existing one

        Parameters
        ----------
        config_values: dict
            Values for the Specification

        allow_update: bool
            Allow updating existing templates

        Returns
        -------
        out_dict: dict
            The updated and loaded objects
        """
        spec_name = config_values["name"]
        namespaced_spec_name = str(uuid5(namespace, spec_name))

        specification = self._parent.specification.get_row_by_name(namespaced_spec_name)
        if specification is not None and not allow_update:
            return specification

        logger.info(f"""Loading specification {spec_name} as {namespaced_spec_name}""")

        if specification is None:
            # update specifications dict with namespaced names
            config_values = deep_update(
                config_values,
                {
                    "name": namespaced_spec_name,
                    "spec_aliases": {
                        k: str(uuid5(namespace, v)) for k, v in config_values["spec_aliases"].items()
                    },
                },
            )
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
        namespace: UUID,
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

        namespace: uuid.UUID
            The campaign namespace into which the specification objects are
            loaded.

        Returns
        -------
        out_dict: dict
            The updated and loaded objects
        """
        if loaded_specs is None:
            loaded_specs = {}

        with open(yaml_file, encoding="utf-8") as f:
            spec_data = yaml.safe_load(f)

        out_dict: dict[str, list[BaseModel]] = dict(
            Specification=[],
            SpecBlock=[],
        )

        for config_item in spec_data:
            # Recursively load any spec YAMLs by dereferencing any Imports
            if "Imports" in config_item:
                imports = config_item["Imports"]
                for import_ in imports:
                    imported_ = self.specification_cl(
                        os.path.abspath(os.path.expandvars(import_)),
                        loaded_specs,
                        allow_update=allow_update,
                        namespace=namespace,
                    )
                    for key, val in imported_.items():
                        out_dict[key] += val
            elif "SpecBlock" in config_item:
                spec_block = self._upsert_spec_block(
                    config_item["SpecBlock"],
                    loaded_specs,
                    allow_update=allow_update,
                    namespace=namespace,
                )
                out_dict["SpecBlock"].append(spec_block)
            elif "Specification" in config_item:
                specification = self._upsert_specification(
                    config_item["Specification"],
                    allow_update=allow_update,
                    namespace=namespace,
                )
                out_dict["Specification"].append(specification)
            else:  # pragma: no cover
                good_keys = "SpecBlock | Specification | Imports"
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
            Yaml file with campaign overrides (a "start" file)

        yaml_file: str
            Optional yaml file with specifications

        Note
        ----
        The keywords optionally override values from the config_file

        Keywords
        --------
        name: str | None
            Name for the campaign

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
        with open(campaign_yaml, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        try:
            manifest = config_data["Campaign"]
        except KeyError as msg:
            raise CMYamlParseError(
                f"Could not find 'Campaign' tag in {campaign_yaml}",
            ) from msg

        assert isinstance(manifest, dict)
        if "data" not in manifest:
            manifest["data"] = {}
        # establish campaign namespace uuid
        spec_name = manifest["spec_name"]
        namespace = uuid5(DEFAULT_NAMESPACE, manifest["name"])
        namespaced_spec_name = str(uuid5(namespace, spec_name))
        manifest["spec_block_assoc_name"] = f"{namespaced_spec_name}#campaign"
        # assert the the loaded campaign is using namespaced objects
        manifest["data"]["namespace"] = str(namespace)
        logger.info(f"""Loading campaign {manifest["name"]} with namespace {namespace}""")

        # TODO deprecate this code path, are "already existing" specifications
        #      allowed? Or is this allowed to invoke a "clone" operation where
        #      some set of "standard" specblocks are already seeded in the DB
        #      but not allowed to be used directly by campaigns?
        if yaml_file is None:  # pragma: no cover
            # If yaml_file isn't given then the specifications
            # should already exist
            specification = self._parent.specification.get_row_by_name(namespaced_spec_name)
            if specification is None:
                raise CMYamlParseError(
                    f"Could not find 'Specification' {spec_name} in {campaign_yaml}",
                )
        else:
            self.specification_cl(yaml_file, namespace=namespace)

        # Creates the campaign record in the DB using the API, returning the
        # campaign via the response model
        manifest["spec_name"] = namespaced_spec_name
        campaign = self._parent.campaign.create(**manifest)

        # For each campaign step, the spec_block reference must be updated with
        # the namespaced spec name. This only applies to the cases where a
        # campaign YAML has step-overrides configured OTT of its "include"
        # campaign.
        # TODO no examples of this pattern in use
        if step_configs := manifest.pop("steps", []):
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
