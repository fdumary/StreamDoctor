from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request


class AuthRateLimiter:
    """Per-process/IP limit for the single-worker demo. No proxy-header trust."""

    def __init__(self, limit: int, window: int):
        self.limit = limit
        self.window = window
        self.buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self.lock = Lock()

    def check(self, key: str) -> None:
        now = monotonic()
        with self.lock:
            bucket = self.buckets.setdefault(key, deque())
            while bucket and bucket[0] <= now - self.window:
                bucket.popleft()
            self.buckets.move_to_end(key)
            if len(bucket) >= self.limit:
                raise HTTPException(
                    429,
                    "Too many authentication attempts. Try again later.",
                    headers={"Retry-After": str(self.window)},
                )
            bucket.append(now)
            # Bound memory for a demo server; use a shared limiter at larger scale.
            if len(self.buckets) > 10000:
                self.buckets.popitem(last=False)


def limit_auth(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    request.app.state.auth_limiter.check(key)
