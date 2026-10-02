"""LLM Gateway exceptions."""

from __future__ import annotations

from omni_core.errors import GuardViolation, OmniError


class LLMError(OmniError):
    """Base exception for LLM gateway errors."""


class CircuitBreakerOpenError(LLMError):
    """Raised when a request is attempted while the circuit breaker is OPEN."""

    def __init__(self, key: str, *, details: str = "") -> None:
        super().__init__(f"Circuit breaker is OPEN for {key}", details=details)
        self.key = key


class SchemaRepairError(LLMError):
    """Raised when structured output validation fails after maximum repair attempts."""

    def __init__(self, attempts: int, last_error: str, *, details: str = "") -> None:
        msg = f"Failed to generate valid structured output after {attempts} repair attempts: {last_error}"
        super().__init__(msg, details=details)
        self.attempts = attempts
        self.last_error = last_error


class ReaderToolBindingError(GuardViolation):
    """Raised when tools are bound to a READER role request (ARCHITECTURE §8)."""

    def __init__(self, details: str = "") -> None:
        super().__init__(
            guard="READER_NO_TOOLS",
            details=details or "READER role LLM calls must have NO tools bound.",
        )


class ProviderError(LLMError):
    """Raised when an underlying LLM provider call fails."""
