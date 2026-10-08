"""Tenant retry budgets with fixed-window rollover."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class RetryBudget:
    capacity: int
    window_seconds: int = 60
    _retry_times: deque[float] = field(default_factory=deque)

    def __post_init__(self) -> None:
        if self.capacity < 1 or self.window_seconds < 1:
            raise ValueError("capacity and window_seconds must be positive")

    def allow_retry(self, now: float) -> bool:
        """Consume one slot after evicting retries outside the active window."""
        cutoff = now - self.window_seconds
        while self._retry_times and self._retry_times[0] <= cutoff:
            self._retry_times.popleft()
        if len(self._retry_times) >= self.capacity:
            return False
        self._retry_times.append(now)
        return True

    def remaining_at(self, now: float) -> int:
        cutoff = now - self.window_seconds
        active = sum(timestamp > cutoff for timestamp in self._retry_times)
        return max(0, self.capacity - active)
