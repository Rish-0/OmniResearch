"""Redaction helper to ensure no secrets enter code, prompts, logs, or sandboxes (Non-negotiable Rule 9)."""

from __future__ import annotations

import re
from typing import Any

# Regex patterns matching common secrets and sensitive strings
SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9\-_]{20,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[a-zA-Z0-9\-_.]+", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"(api[_-]?key|secret|password|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9\-_.]+)['\"]?", re.IGNORECASE),
]

SENSITIVE_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r".*(key|secret|token|password|auth|credential).*", re.IGNORECASE),
]


class Redactor:
    """Redacts secrets and sensitive information from text, lists, and dicts."""

    def __init__(self, custom_patterns: list[re.Pattern[str]] | None = None) -> None:
        self.patterns = SECRET_PATTERNS + (custom_patterns or [])

    def redact_text(self, text: str) -> str:
        """Redact secrets from a text string."""
        if not text:
            return text

        result = text
        for pattern in self.patterns:
            result = pattern.sub("[REDACTED_SECRET]", result)
        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact secrets from dictionary values and key matches."""
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            if any(p.match(key) for p in SENSITIVE_KEY_PATTERNS):
                redacted[key] = "[REDACTED_SECRET]"
            elif isinstance(value, str):
                redacted[key] = self.redact_text(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self.redact_dict(item) if isinstance(item, dict)
                    else self.redact_text(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted
