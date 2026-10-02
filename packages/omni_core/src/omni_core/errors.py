"""Error hierarchy for OmniResearch."""

from __future__ import annotations


class OmniError(Exception):
    """Base error for all OmniResearch exceptions."""

    def __init__(self, message: str, *, details: str = "") -> None:
        super().__init__(message)
        self.details = details


class BudgetExceeded(OmniError):
    """Raised when a budget limit is exceeded."""

    def __init__(
        self,
        resource: str,
        limit: float,
        current: float,
        *,
        details: str = "",
    ) -> None:
        msg = f"Budget exceeded for {resource}: {current:.2f} >= {limit:.2f}"
        super().__init__(msg, details=details)
        self.resource = resource
        self.limit = limit
        self.current = current


class GuardViolation(OmniError):
    """Raised when a safety guard is triggered."""

    def __init__(self, guard: str, *, details: str = "") -> None:
        super().__init__(f"Guard violation: {guard}", details=details)
        self.guard = guard


class SandboxViolation(OmniError):
    """Raised when sandbox security is violated."""


class ReplanRejected(OmniError):
    """Raised when a replan is rejected (e.g. duplicate fingerprint, no-op delta)."""


class VerificationError(OmniError):
    """Raised on verification failures (fail-closed)."""
