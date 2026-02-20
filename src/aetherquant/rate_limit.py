from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic


@dataclass(slots=True)
class _Bucket:
    timestamps: deque[float] = field(default_factory=deque)


class InMemoryRateLimiter:
    """Simple fixed-window limiter for API protection."""

    def __init__(self, limit_per_minute: int) -> None:
        if limit_per_minute <= 0:
            raise ValueError("limit_per_minute must be greater than zero")
        self.limit_per_minute = limit_per_minute
        self._buckets: dict[str, _Bucket] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> tuple[bool, float]:
        current = monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket())
            window_start = current - 60.0
            while bucket.timestamps and bucket.timestamps[0] <= window_start:
                bucket.timestamps.popleft()

            if len(bucket.timestamps) >= self.limit_per_minute:
                retry_after = max(0.0, 60.0 - (current - bucket.timestamps[0]))
                return False, retry_after

            bucket.timestamps.append(current)
            return True, 0.0
