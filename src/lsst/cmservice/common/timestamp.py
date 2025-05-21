"""Module for utility functions or classes related to obtaining or manipulating
timestamps.
"""

import datetime as dt


def element_time() -> int:
    """Produce an epoch timestamp useful for including in a campaign element's
    ``crtime`` or `mtime` metadata entry.
    """
    return int(dt.datetime.now().timestamp())
