"""String parsing module for CM Service."""

import re

from ..common.errors import CMBadFullnameError


def parse_element_fullname(fullname: str) -> dict:
    """Parse a /-delimited fullname into named fields

    Parameters
    ---------
    fullname: str
        String to be parsed

    Returns
    -------
    fields : dict
        Resulting fields
    """
    fullname_r = re.compile(
        (
            r"^"
            r"(?P<campaign>[\w]+){1}(?:\/)*"
            r"(?P<step>[\w]+){0,1}(?:\/)*"
            r"(?P<group>[\w]+){0,1}(?:\/)*"
            r"(?P<job>[\w]+){0,1}(?:\/)*"
            r"(?P<script>[\w]+){0,1}"
            r"$"
        ),
        re.MULTILINE,
    )
    fields = {"production": "DEFAULT"}

    if (match := re.match(fullname_r, fullname)) is None:
        raise CMBadFullnameError(f"Fullname {fullname} is not parseable")

    for k, v in match.groupdict().items():
        fields[k] = v

    return fields
