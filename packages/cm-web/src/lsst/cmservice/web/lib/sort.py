from typing import Any


def manifest_sort(manifest: dict[str, Any]) -> tuple[int, str]:
    """Sort key function for a list of manifests such that campaigns are sorted
    first, edges, last, and everything else in between.
    """
    match manifest["kind"]:
        case "campaign":
            return (0, "campaign")
        case "edge":
            return (2, "edge")
        case _ as kind:
            return (1, kind)
