"""Exponential backoff decorator with jitter."""

import functools
import random
import time
import logging

from config.constants import (
    RETRY_BASE_SECONDS,
    RETRY_MAX_SECONDS,
    RETRY_MAX_ATTEMPTS,
    RETRY_JITTER_FACTOR,
)

log = logging.getLogger(__name__)


def retry(
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    base_seconds: float = RETRY_BASE_SECONDS,
    max_seconds: float = RETRY_MAX_SECONDS,
    jitter: float = RETRY_JITTER_FACTOR,
    exceptions: tuple = (Exception,),
):
    """Retry decorator with exponential backoff and jitter."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        log.error(
                            "retry exhausted for %s after %d attempts: %s",
                            fn.__name__,
                            max_attempts,
                            exc,
                        )
                        raise
                    delay = min(base_seconds * (2 ** (attempt - 1)), max_seconds)
                    delay *= 1 + random.uniform(-jitter, jitter)
                    log.warning(
                        "retry %s attempt %d/%d failed (%s), sleeping %.1fs",
                        fn.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
            raise last_exc  # unreachable but satisfies type checkers

        return wrapper

    return decorator
