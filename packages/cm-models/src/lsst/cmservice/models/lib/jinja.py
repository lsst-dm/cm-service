import random
from collections.abc import Callable, Mapping
from datetime import datetime
from string import ascii_letters, digits
from typing import Literal

# Jinja Filter functions
# All filter functions should take at least one positional `value` argument.


def as_lsst_version(value: datetime, format: Literal["weekly", "daily"] = "weekly") -> str:
    """Given a datetime input, construct a "weekly" LSST version."""
    match format:
        case "weekly":
            return f"{value:w_%G_%V}"
        case "daily":
            return f"{value:d_%Y_%m_%d}"


def as_day_obs(value: datetime) -> str:
    """Given a datetime input, construct an "day_obs" format"""
    return f"{value:%Y%m%d}"


def as_exposure(value: datetime, exposure: int = 0) -> str:
    """Given a datetime, return a string in the format of "day_obs" followed by
    an exposure number, zero-padded to 5 digits.
    """
    return f"{value:%Y%m%d}{exposure:05d}"


def in_(value: list[str | int | float], *, field: str, not_in: bool = False) -> str:
    """Given a value list, return a string usable as a SQL IN clause, as for
    use in a Butler data query predicate.
    """
    # Because this is a SQL predicate, strip any residual quotes from the value
    # and replace them cleanly with single quotes when the value is a string.
    SINGLE_QUOTE = "'"
    DOUBLE_QUOTE = '"'
    EMPTY_STRING = ""
    translation_table = str.maketrans(EMPTY_STRING, EMPTY_STRING, f"{SINGLE_QUOTE}{DOUBLE_QUOTE}")
    in_list: list[str] = [
        f"'{v.translate(translation_table)}'" if isinstance(v, str) else str(v) for v in value
    ]
    return f"{field} {'NOT ' if not_in else ''}IN ({','.join(in_list)})"


def not_in_(value: list[str | int | float], *, field: str) -> str:
    """Given a value list, return a string usable as a SQL IN clause, as for
    use in a Butler data query predicate.
    """
    return in_(value, field=field, not_in=True)


def random_n(value: str, n: int) -> str:
    """Return a random string of length n joined by the passed value."""
    return value.join(random.choices(ascii_letters + digits, k=n))


# All filters as a mapping constant
FILTERS: Mapping[str, Callable] = {
    "as_lsst_version": as_lsst_version,
    "as_day_obs": as_day_obs,
    "as_exposure": as_exposure,
    "sql_in": in_,
    "sql_not_in": not_in_,
    "random_n": random_n,
}
