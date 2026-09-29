from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Small single-process limiter for the laptop/self-hosted deployment profile."""

    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    def consume(self, key: str, *, limit: int, window_seconds: float) -> tuple[bool, int]:
        if limit < 1 or window_seconds <= 0:
            return False, max(1, int(window_seconds))
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            queue = self._windows[key]
            while queue and queue[0] <= cutoff:
                queue.popleft()
            if len(queue) >= limit:
                retry_after = max(1, int(queue[0] + window_seconds - now + 0.999))
                return False, retry_after
            queue.append(now)
            return True, 0


limiter = SlidingWindowLimiter()
