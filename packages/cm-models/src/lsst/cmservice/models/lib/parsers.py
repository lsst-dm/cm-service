import os
import re


def as_snake_case(s: str) -> str:
    """Preprocess a string by sanitizing it and producing snake case."""
    # TODO clean up unicode characters and etc
    return re.sub(r"\W+?", "_", s)


def as_templated_snake_case(s: str) -> str:
    """Preprocess a string by sanitizing it and producing snake case while
    preserving template variable placeholders.
    """
    pattern = r"(?<!\$)\{\{.*?\}\}|\W"
    return re.sub(pattern, lambda x: x.group(0) if x.group(0).startswith("{{") else "_", s)


def strip_trailing_slash(s: str) -> str:
    """Preprocess a string by stripping any trailing separator character."""
    return s.rstrip(os.sep)
