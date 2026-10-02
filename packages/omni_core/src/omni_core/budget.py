"""Budget tracker for resource usage across a research session."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from omni_core.errors import BudgetExceeded


@dataclass
class BudgetTracker:
    """Thread-safe budget tracker that raises BudgetExceeded when limits are hit.

    Each resource tracks current usage against a configured limit.
    """

    limits: dict[str, float] = field(default_factory=dict)
    _usage: dict[str, float] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_limit(self, resource: str, limit: float) -> None:
        """Set or update a limit for a resource."""
        with self._lock:
            self.limits[resource] = limit
            if resource not in self._usage:
                self._usage[resource] = 0.0

    def record(self, resource: str, amount: float) -> None:
        """Record usage of a resource. Raises BudgetExceeded if limit is hit."""
        with self._lock:
            current = self._usage.get(resource, 0.0) + amount
            limit = self.limits.get(resource)
            if limit is not None and current >= limit:
                raise BudgetExceeded(resource=resource, limit=limit, current=current)
            self._usage[resource] = current

    def usage(self, resource: str) -> float:
        """Get current usage of a resource."""
        with self._lock:
            return self._usage.get(resource, 0.0)

    def remaining(self, resource: str) -> float | None:
        """Get remaining budget for a resource, or None if unlimited."""
        with self._lock:
            limit = self.limits.get(resource)
            if limit is None:
                return None
            return limit - self._usage.get(resource, 0.0)

    def check(self, resource: str, amount: float = 0.0) -> bool:
        """Check if recording `amount` would exceed the budget without recording."""
        with self._lock:
            limit = self.limits.get(resource)
            if limit is None:
                return True
            return self._usage.get(resource, 0.0) + amount < limit

    def reset(self, resource: str | None = None) -> None:
        """Reset usage. If resource is None, reset all."""
        with self._lock:
            if resource is None:
                for key in self._usage:
                    self._usage[key] = 0.0
            else:
                self._usage[resource] = 0.0
