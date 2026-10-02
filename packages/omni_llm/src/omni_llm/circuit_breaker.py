"""Circuit breaker pattern for LLM providers and model endpoints."""

from __future__ import annotations

import time
from enum import StrEnum, unique

from omni_llm.exceptions import CircuitBreakerOpenError


@unique
class CircuitState(StrEnum):
    """States of the circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit breaker for guarding against cascading LLM provider failures.

    Transitions:
    - CLOSED -> OPEN: when consecutive_failures >= failure_threshold
    - OPEN -> HALF_OPEN: when recovery_timeout seconds have elapsed since tripping
    - HALF_OPEN -> CLOSED: when half_open_successes >= half_open_max_calls
    - HALF_OPEN -> OPEN: on any failure during HALF_OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 2,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, updating from OPEN to HALF_OPEN if timeout passed."""
        if (
            self._state == CircuitState.OPEN
            and time.time() - self._last_failure_time >= self.recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_successes = 0
        return self._state

    def check_allowed(self) -> None:
        """Check if execution is allowed. Raises CircuitBreakerOpenError if OPEN."""
        if self.state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                self.name,
                details=f"Failure threshold ({self.failure_threshold}) reached. Circuit OPEN.",
            )

    def record_success(self) -> None:
        """Record a successful request."""
        current_state = self.state
        if current_state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_max_calls:
                self._reset()
        elif current_state == CircuitState.CLOSED:
            self._consecutive_failures = 0

    def record_failure(self, _error: Exception | None = None) -> None:
        """Record a failed request."""
        self._consecutive_failures += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN or self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def _reset(self) -> None:
        """Reset state back to CLOSED."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._half_open_successes = 0
        self._last_failure_time = 0.0
