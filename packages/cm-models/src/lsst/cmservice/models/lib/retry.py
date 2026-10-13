import asyncio
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Protocol


class RetryConfig(Protocol):
    """Configuration protocol for a retry operation.

    Parameters
    ----------
    delay : ``float``
        Initial time to wait between tries, in seconds.

    tries: ``int``
        Total number of attempts to make, including the initial try.

    backoff: ``float``
        Multiplicative factor for increasing the delay between tries.

    retryables: ``list`` [``str``]
        A list of exception names that if raised by the payload are subject
        to retries. If empty, retries are not constrained by exception name.
    """

    delay: float | int = 5
    tries: int = 3
    backoff: float = 1.5


def exponential_retry[**P, T](
    config: RetryConfig,
    *,
    retryables: list[str] = [],
    callback: Callable[..., Awaitable] | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T | None]]]:
    """Decorator factory for applying a retry mechanism to an async function

    Parameters
    ----------
    config: ``RetryConfig``
        Any object that implements the ``RetryConfig`` protocol.

    retryables: ``list`` [``str``]
        A list of exception names that if raised by the payload are subject
        to retries. If empty, retries are not constrained by exception name.

    callback: ``Callable`` | ``None``
        If provided, should be a coro to invoke for each retry iteration.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T | None]]:
        """Decorator wraps async function with a retry mechanism"""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | None:
            """Wraps async function with a retry mechanism"""
            evt = asyncio.Event()
            r = None
            _backoff = config.backoff
            _delay = config.delay
            _tries = config.tries
            _callback = callback
            while not evt.is_set():
                try:
                    r = await func(*args, **kwargs)
                    evt.set()
                except Exception as exc:
                    if type(exc).__name__ not in retryables:
                        raise
                    elif _tries <= 0:
                        raise
                    else:
                        if _callback is not None:
                            await _callback(exc)
                        _delay *= _backoff
                        await asyncio.sleep(_delay)
                        _tries -= 1
            return r

        return wrapper

    return decorator
