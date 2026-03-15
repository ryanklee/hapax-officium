"""Simple in-memory rate limiter for cockpit API endpoints.

No external dependencies — uses a dict of timestamps. Designed for a
single-operator system; protects against accidental runaway clients,
not adversarial DDoS.
"""

from __future__ import annotations

import functools
import time
from collections import defaultdict

from fastapi import HTTPException

# bucket_name → list of request timestamps (monotonic)
_buckets: dict[str, list[float]] = defaultdict(list)


def _check(bucket: str, max_calls: int, window_s: float) -> None:
    """Raise 429 if the bucket has exceeded max_calls within window_s."""
    now = time.monotonic()
    timestamps = _buckets[bucket]

    # Prune expired entries
    cutoff = now - window_s
    _buckets[bucket] = [t for t in timestamps if t > cutoff]
    timestamps = _buckets[bucket]

    if len(timestamps) >= max_calls:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({max_calls} requests per {int(window_s)}s)",
        )
    timestamps.append(now)


def rate_limit(bucket: str, *, max_calls: int = 10, window_s: float = 60.0):
    """Decorator that applies a per-bucket rate limit to a FastAPI endpoint.

    Usage::

        @router.post("/expensive")
        @rate_limit("expensive_op", max_calls=5, window_s=60)
        async def expensive(req: SomeModel):
            ...

    Must be applied *after* the router decorator so it wraps the function
    before FastAPI inspects its signature.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            _check(bucket, max_calls, window_s)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def reset_buckets() -> None:
    """Clear all rate limit state (for testing)."""
    _buckets.clear()
