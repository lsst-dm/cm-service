"""CM Service yaml constructors"""

import os

import yaml


def resolved_string_constructor(loader: yaml.SafeLoader, node: yaml.nodes.ScalarNode) -> str:
    """A custom constructor for '!!str' YAML tags that will update any variable
    references in the value.
    """
    initial_value = str(loader.construct_scalar(node))
    resolved_value = os.path.expandvars(initial_value)
    return resolved_value


def get_loader() -> type[yaml.SafeLoader]:
    """Gets a YAML SafeLoader with a custom string constructor that can auto-
    matically resolve '${...}' and '$...' variable references.
    """
    loader = yaml.SafeLoader
    loader.add_constructor("tag:yaml.org,2002:str", resolved_string_constructor)
    return loader


def str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    str_tag = "tag:yaml.org,2002:str"
    if "\n" in data:
        return dumper.represent_scalar(str_tag, data, style="|")
    else:
        return dumper.represent_scalar(str_tag, data)
