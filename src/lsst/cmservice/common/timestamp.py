"""Module for utility functions or classes related to obtaining or manipulating
timestamps.
"""

import datetime as dt


def element_time() -> int:
    """Produce an epoch timestamp useful for including in a campaign element's
    ``crtime`` or `mtime` metadata entry.
    """
    return int(dt.datetime.now(tz=dt.UTC).timestamp())


def bps_timestamp(timestamp: int) -> str:
    """Produce a bps-alike timestamp string from an epoch time.

    Returns
    -------
    str
        A datetime formatted as YYYYmmddTHHMMSSZ (with no punctuation)
    """
    return dt.datetime.fromtimestamp(timestamp).astimezone(tz=dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def iso_timestamp(timestamp: int) -> str:
    """Produce an ISO8601 or RFC3339 timestamp string from an epoch time.

    Returns
    -------
    str
        A datetime formatted as YYYY-mm-ddTHH:MM:SSZ
    """
    return dt.datetime.fromtimestamp(timestamp).astimezone(tz=dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
