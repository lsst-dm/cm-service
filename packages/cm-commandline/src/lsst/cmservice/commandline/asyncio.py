import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any


def async_command(f: Callable) -> Any:
    """General-purpose decorator that runs the sync function in an asyncio
    event loop.
    """

    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))

    return wrapper
