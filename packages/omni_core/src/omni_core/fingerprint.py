"""Failure fingerprinting for replan loop prevention.

Produces a deterministic fingerprint from (failure_class, error_signature, spec_hash)
after normalizing volatile tokens (paths, IPs, timestamps, memory addresses).
"""

from __future__ import annotations

import hashlib
import re

# Patterns for volatile tokens that should be normalised
_VOLATILE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # File paths (Unix & Windows)
    (re.compile(r"(?:/[\w./-]+)+"), "<PATH>"),
    (re.compile(r"[A-Za-z]:\\[\w.\\-]+"), "<PATH>"),
    # IP addresses
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<IP>"),
    # Timestamps (ISO 8601 and common formats)
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TS>"),
    # Memory addresses
    (re.compile(r"0x[0-9a-fA-F]{6,16}"), "<ADDR>"),
    # UUIDs
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE), "<UUID>"),
    # Port numbers in URLs
    (re.compile(r":\d{4,5}(?=/)"), ":<PORT>"),
    # PID / large integers that look like process ids
    (re.compile(r"\bpid[= ]\d+\b"), "pid=<PID>"),
]


def _normalise(text: str) -> str:
    """Replace volatile tokens with stable placeholders."""
    result = text
    for pattern, replacement in _VOLATILE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def fingerprint(failure_class: str, error_signature: str, spec_hash: str = "") -> str:
    """Compute a deterministic failure fingerprint.

    Args:
        failure_class: The FailureClass enum value.
        error_signature: The error message or signature to normalise.
        spec_hash: Optional spec hash for experiment-related failures.

    Returns:
        A hex SHA-256 fingerprint string.
    """
    normalised_sig = _normalise(error_signature)
    composite = f"{failure_class}|{normalised_sig}|{spec_hash}"
    return hashlib.sha256(composite.encode()).hexdigest()
