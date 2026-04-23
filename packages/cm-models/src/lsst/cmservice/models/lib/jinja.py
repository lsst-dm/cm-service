from collections.abc import Callable, Mapping
from datetime import datetime
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


def as_obs_day(value: datetime) -> str:
    """Given a datetime input, construct an "obs_day" format"""
    return f"{value:%Y%m%d}"


def as_exposure(value: datetime, exposure: int = 0) -> str:
    return f"{value:%Y%m%d}{exposure:05d}"


# All filters as a mapping constant
FILTERS: Mapping[str, Callable] = {
    "as_lsst_version": as_lsst_version,
    "as_obs_day": as_obs_day,
    "as_exposure": as_exposure,
}
