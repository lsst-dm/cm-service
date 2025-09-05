from __future__ import annotations

import os
import warnings
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid5

import httpx
import yaml
from pydantic.v1.utils import deep_update

from .. import models
from ..common.enums import DEFAULT_NAMESPACE, ErrorActionEnum, ErrorFlavorEnum, ErrorSourceEnum
from ..common.errors import CMMissingFullnameError, CMYamlParseError
from ..common.logging import LOGGER
from ..common.yaml import get_loader
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
        namespace: UUID | None,
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

        Raises
        ------
        CMMissingFullnameError
            If the spec depends on another spec that cannot be located.
        """
        spec_name: str = spec["name"]
        key = str(uuid5(namespace, spec_name)) if namespace else spec_name

        spec_block = self._parent.spec_block.get_row_by_name(key)
        if spec_block and not allow_update:
            return spec_block

        logger.info("Loading spec_block %s as %s", spec_name, key)

        # A spec that "includes" another spec is effectively declaring a clone
        # of the referenced spec that should have already been "loaded" such
        # that we can dereference it from the loaded_specs mapping

        # the list of spec names to "include"
        includes = spec.get("includes", [])

        # the new spec as a shallow copy of its input
        block_data = spec.copy()

        # a mapping to contain any/all "included" spec data
        include_data: dict[str, Any] = {}
        for include_ in includes:
            namespaced_spec = str(uuid5(namespace, include_)) if namespace else include_

            # The case where the include pointer has already been encount-
            # ered by the loader and can be referenced directly by name or a
            # namespaced uuid
            if namespaced_spec in loaded_specs:
                include_data = deep_update(include_data, loaded_specs[namespaced_spec])
            elif include_ in loaded_specs and not isinstance(loaded_specs[include_], int):
                include_data = deep_update(include_data, loaded_specs[include_])
            # The case where the spec blocks are defined out of order in
            # the specification file and it is not yet part of the loaded
            # specs mapping.
            else:  # pragma: no cover
                raise CMMissingFullnameError

        block_data = deep_update(include_data, spec)

        # the block data deep references to other spec_blocks by name need to
        # be updated with namespaced names in child_config, scripts, & steps
        if "child_config" in block_data:
            block_data["child_config"] = deep_update(
                block_data["child_config"],
                {
                    k: str(uuid5(namespace, v)) if namespace else v
                    for k, v in block_data["child_config"].items()
                    if k == "spec_block"
                },
            )

        handler = block_data.get("handler")
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
        namespace: UUID | None,
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
        namespaced_spec_name = str(uuid5(namespace, spec_name)) if namespace else spec_name

        specification = self._parent.specification.get_row_by_name(namespaced_spec_name)
        if specification is not None and not allow_update:
            return specification

        logger.info("Loading specification %s as %s", spec_name, namespaced_spec_name)

        if specification is None:
            # update specifications dict with namespaced names
            config_values = deep_update(
                config_values,
                {
                    "name": namespaced_spec_name,
                    "spec_aliases": {
                        k: str(uuid5(namespace, v)) if namespace else v
                        for k, v in config_values["spec_aliases"].items()
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
        yaml_file: deque[dict] | str,
        loaded_specs: dict | None = None,
        *,
        allow_update: bool = False,
        namespace: UUID | None = None,
    ) -> dict:
        """Create Specification objects

        Parameters
        ----------
        yaml_file: Iterable | str
            YAML file to load, or an iterable of specs

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

        if isinstance(yaml_file, str):
            with Path(yaml_file).open(encoding="utf-8") as f:
                spec_data: deque[dict] = deque(yaml.safe_load(f))
        else:
            spec_data = yaml_file

        out_dict: dict[str, list[BaseModel]] = dict(
            Specification=[],
            SpecBlock=[],
        )

        while spec_data:
            config_item = spec_data.popleft()
            # Recursively load any spec YAMLs by dereferencing any Imports
            if "Imports" in config_item:
                imports = config_item["Imports"]
                for import_ in imports:
                    import_path = Path(os.path.expandvars(import_)).resolve()
                    with import_path.open(encoding="utf-8") as f:
                        for import_item in yaml.safe_load(f):
                            spec_data.appendleft(import_item)
            elif "SpecBlock" in config_item:
                try:
                    spec_block = self._upsert_spec_block(
                        config_item["SpecBlock"],
                        loaded_specs,
                        allow_update=allow_update,
                        namespace=namespace,
                    )
                    loaded_specs[spec_block.name] = config_item["SpecBlock"]
                    out_dict["SpecBlock"].append(spec_block)
                except CMMissingFullnameError:
                    # move this item to the end of the list to try again later
                    # up to three times
                    try_count = loaded_specs.get(config_item["SpecBlock"]["name"], 0)
                    if isinstance(try_count, int):
                        try_count += 1
                        if try_count > 3:
                            logger.error(
                                "Can't find all dependencies for spec block after multiple tries.",
                                spec_block=config_item["SpecBlock"]["name"],
                                tries=try_count,
                            )
                            raise RuntimeError("Failed to locate all spec dependencies in input.")
                        logger.warning(
                            "Can't find all dependencies for spec block, trying later.",
                            spec_block=config_item["SpecBlock"]["name"],
                            tries=try_count,
                        )
                        spec_data.append(config_item)
                        loaded_specs[config_item["SpecBlock"]["name"]] = try_count
                    else:
                        logger.error("this is weird.")

            elif "Specification" in config_item:
                specification = self._upsert_specification(
                    config_item["Specification"],
                    allow_update=allow_update,
                    namespace=namespace,
                )
                out_dict["Specification"].append(specification)
            else:  # pragma: no cover
                logger.warning(
                    "Ignoring extra spec type in input data",
                    spec_data=config_item.keys(),
                    expected_keys="SpecBlock | Specification | Imports",
                )

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

        namespace: UUID | None
            Namespace to use for the campaign, defaults to the service default.

        Returns
        -------
        campaign : `Campaign`
            Newly created `Campaign`
        """
        manifest_deque: deque[dict] = deque()
        campaign = None

        # Apply any kwargs and -v pairs to the process environment for
        # resolution in the YAML loader
        campaign_variables = {k: v for k, v in kwargs.pop("v", ())}
        os.environ |= {**campaign_variables, **{k: str(v) for k, v in kwargs.items() if v}}

        if yaml_file is not None:
            _ = self.specification_cl(yaml_file, namespace=kwargs["namespace"])

        with Path(campaign_yaml).open(encoding="utf-8") as f:
            yaml_stack = yaml.load_all(f, Loader=get_loader())

            # sort the manifests into a deque; Campaign overrides first
            for yaml_document in yaml_stack:
                if yaml_document is None:
                    logger.error("Could not find YAML documents in input file", input_file=campaign_yaml)
                    raise RuntimeError
                if "Production" in yaml_document:
                    warnings.warn(
                        "Production object in campaign YAML file is deprecated, ignoring.", DeprecationWarning
                    )
                if "Campaign" in yaml_document:
                    manifest_deque.appendleft(yaml_document["Campaign"])
                else:
                    # put the individual specblocks onto the deque as manifests
                    for manifest in yaml_document:
                        manifest_deque.append(manifest)

        config_data = manifest_deque.popleft()

        try:
            manifest = config_data
        except KeyError as e:
            msg = f"Could not find 'Campaign' tag in {campaign_yaml}"
            raise CMYamlParseError(msg) from e

        assert isinstance(manifest, dict)
        if "data" not in manifest:
            manifest["data"] = {}
        if "collections" not in manifest:
            manifest["collections"] = {}

        # flesh out config_data with kwarg overrides
        for key in ["name"]:
            val = kwargs.get(key, None)
            if val:
                manifest[key] = val

        manifest["data"]["lsst_version"] = campaign_variables.get("LSST_VERSION", "w_latest")

        if any(
            [
                "MUST_OVERRIDE" in manifest.values(),
                "MUST_OVERRIDE" in manifest["data"].values(),
                "MUST_OVERRIDE" in manifest["collections"].values(),
            ]
        ):
            raise RuntimeError("Found a MUST_OVERRIDE placeholder in input file")

        # establish campaign namespace uuid
        spec_name = manifest["spec_name"]
        namespace = kwargs.get("namespace") or uuid5(DEFAULT_NAMESPACE, manifest["name"])
        namespaced_spec_name = str(uuid5(namespace, spec_name))
        manifest["spec_block_assoc_name"] = f"{namespaced_spec_name}#campaign"
        # assert the the loaded campaign is using namespaced objects
        manifest["data"]["namespace"] = str(namespace)
        logger.info("Loading campaign %s with namespace %s", manifest["name"], namespace)

        # Load the remaining manifests as lists of specblocks
        loaded_specs: dict[str, Any] = {}
        self.specification_cl(manifest_deque, loaded_specs, namespace=namespace)

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
        with Path(yaml_file).open(encoding="utf-8") as fin:
            error_types = yaml.safe_load(fin)

        ret_list: list[models.PipetaskErrorType] = []
        for error_type_ in error_types:
            try:
                val = error_type_["PipetaskErrorType"]
            except KeyError as e:
                msg = f"Expecting PipetaskErrorType items not: {error_type_.keys()})"
                raise CMYamlParseError(msg) from e

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
