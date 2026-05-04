import time
from collections import defaultdict

from .errors import RateLimitExceeded


class RateLimiter:
    """
    Simple sliding-window rate limiter.
    """

    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.time()
        cutoff = now - self.window_seconds
        hits = [t for t in self._hits[key] if t >= cutoff]
        if len(hits) >= self.max_requests:
            raise RateLimitExceeded("Rate limit exceeded")
        hits.append(now)
        self._hits[key] = hits