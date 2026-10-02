"""Structured JSON logging with context variables."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables for structured logging
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
task_id_var: ContextVar[str] = ContextVar("task_id", default="")
agent_var: ContextVar[str] = ContextVar("agent", default="")
attempt_no_var: ContextVar[int] = ContextVar("attempt_no", default=0)


class StructuredFormatter(logging.Formatter):
    """JSON formatter that includes context variables."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context vars if set
        if trace_id := trace_id_var.get(""):
            log_entry["trace_id"] = trace_id
        if session_id := session_id_var.get(""):
            log_entry["session_id"] = session_id
        if task_id := task_id_var.get(""):
            log_entry["task_id"] = task_id
        if agent := agent_var.get(""):
            log_entry["agent"] = agent
        if attempt_no := attempt_no_var.get(0):
            log_entry["attempt_no"] = attempt_no

        # Add exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            extra_fields = record.extra_fields
            if isinstance(extra_fields, dict):
                log_entry.update(extra_fields)

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configure root logger with structured output."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s | %(message)s")
        )

    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"omni.{name}")
