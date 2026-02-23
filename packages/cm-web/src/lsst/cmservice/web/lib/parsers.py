import re


def as_snake_case(s: str) -> str:
    """Preprocesses a string by sanitizing it and producing snake case."""
    # TODO clean up unicode characters and etc
    return re.sub(r"\W+?", "_", s)
