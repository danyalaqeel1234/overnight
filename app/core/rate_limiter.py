import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple


class RollingRateLimiter:
    """
    Rolling window rate limiter: 100 requests per 10 seconds per IP.
    Only applies to /api/v1/* paths. Rejected requests are NOT counted.
    """

    def __init__(self, limit: int = 100, window_seconds: float = 10.0):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, ip: str, now: Optional[float] = None) -> Tuple[bool, int]:
        t = time.time() if now is None else now
        cutoff = t - self.window_seconds
        window = self.requests[ip]

        while window and window[0] <= cutoff:
            window.popleft()

        if len(window) < self.limit:
            window.append(t)
            return True, 0
        else:
            oldest = window[0]
            retry_after = max(1, int(oldest + self.window_seconds - t + 0.999))
            return False, retry_after

    def reset(self):
        self.requests.clear()
