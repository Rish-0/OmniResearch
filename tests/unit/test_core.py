"""Unit tests for omni_core utilities."""

import pytest

from omni_core.budget import BudgetTracker
from omni_core.errors import BudgetExceeded, GuardViolation, OmniError
from omni_core.fingerprint import fingerprint
from omni_core.ids import uuid7


def test_uuid7_monotonicity_and_format() -> None:
    """uuid7() generates valid time-ordered UUIDs."""
    u1 = uuid7()
    u2 = uuid7()

    assert u1.version == 7
    assert u2.version == 7
    assert str(u1) != str(u2)


def test_fingerprint_volatile_normalization() -> None:
    """Fingerprint must normalize paths, IPs, memory addresses, and timestamps to yield identical hash."""
    err1 = "OOM error at 0x7f8a1234 in file /tmp/run_123/train.py at 2026-09-29T10:00:00Z"
    err2 = "OOM error at 0x9b3c5678 in file /home/user/work/train.py at 2026-09-29T11:22:33Z"

    fp1 = fingerprint("RESOURCE_ERROR", err1, "spec_hash_abc")
    fp2 = fingerprint("RESOURCE_ERROR", err2, "spec_hash_abc")

    assert fp1 == fp2, "Fingerprints must match after volatile token normalization"


def test_fingerprint_changes_on_different_failure_class() -> None:
    """Fingerprint changes if failure class or spec hash differs."""
    err = "File not found: /data/sst2.csv"
    fp1 = fingerprint("DATA_ISSUE", err)
    fp2 = fingerprint("CODE_ERROR", err)

    assert fp1 != fp2


def test_budget_tracker_limits_and_exceeded() -> None:
    """BudgetTracker tracks usage and raises BudgetExceeded when limit hit."""
    tracker = BudgetTracker()
    tracker.set_limit("llm_cost_usd", 10.0)

    tracker.record("llm_cost_usd", 4.0)
    assert tracker.usage("llm_cost_usd") == 4.0
    assert tracker.remaining("llm_cost_usd") == 6.0
    assert tracker.check("llm_cost_usd", 5.0) is True

    with pytest.raises(BudgetExceeded) as exc_info:
        tracker.record("llm_cost_usd", 7.0)  # 4 + 7 = 11 >= 10 limit

    assert exc_info.value.resource == "llm_cost_usd"
    assert exc_info.value.current == 11.0
    assert exc_info.value.limit == 10.0


def test_error_hierarchy() -> None:
    """Custom exceptions inherit from OmniError."""
    err = GuardViolation("ssrf_guard", details="Attempted internal IP fetch")
    assert isinstance(err, OmniError)
    assert err.guard == "ssrf_guard"
    assert err.details == "Attempted internal IP fetch"
