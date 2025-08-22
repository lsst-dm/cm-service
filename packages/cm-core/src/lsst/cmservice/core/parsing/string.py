"""String parsing module for CM Service."""

import re
from dataclasses import asdict, dataclass, fields

from ..common.errors import CMBadFullnameError


@dataclass(order=True)
class Fullname:
    """A dataclass representing an Element's fullname."""

    campaign: str
    step: str | None = None
    group: str | None = None
    job: str | None = None
    script: str | None = None

    def fullname(self) -> str:
        """Returns a /-delimited fullname string"""
        fullname = ""
        for f in fields(self):
            f_value = getattr(self, f.name)
            if f_value is None:
                break
            else:
                fullname += f"/{f_value}"
        return fullname.lstrip("/")

    def model_dump(self) -> dict:
        """Returns dataclass as a dictionary with Nones removed."""
        return {k: v for k, v in asdict(self).items() if v is not None}


def parse_element_fullname(fullname: str) -> Fullname:
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
            r"(?P<campaign>[\w-]+){1}(?:\/)*"
            r"(?P<step>[\w-]+){0,1}(?:\/)*"
            r"(?P<group>[\w-]+){0,1}(?:\/)*"
            r"(?P<job>[\w-]+){0,1}(?:\/)*"
            r"(?P<script>[\w-]+){0,1}"
            r"$"
        ),
        re.MULTILINE,
    )

    if (match := re.match(fullname_r, fullname)) is None:
        raise CMBadFullnameError(f"Fullname {fullname} is not parseable")

    return Fullname(**match.groupdict())
