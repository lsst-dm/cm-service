from typing import Any


def deep_update[T](mapping: dict[T, Any], *updating_mappings: dict[T, Any]) -> dict[T, Any]:
    """Perform a recursive dictionary update.

    Note: this reimplements the deprecated ``pydantic.v1.deep_update`` method.
    """
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if k in updated_mapping and isinstance(updated_mapping[k], dict) and isinstance(v, dict):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping
