"""Unit tests for T03 LLM Gateway (role routing, structured output repair, fallback, circuit breaker, budget, redaction, FakeProvider)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from omni_core.budget import BudgetTracker
from omni_core.errors import BudgetExceeded
from omni_llm.circuit_breaker import CircuitBreaker, CircuitState
from omni_llm.exceptions import (
    CircuitBreakerOpenError,
    ReaderToolBindingError,
    SchemaRepairError,
)
from omni_llm.fake_provider import FakeLLMResponse, FakeProvider
from omni_llm.gateway import LLMGateway
from omni_llm.roles import LLMRole, ModelConfig, RoleRouter


# Pydantic schema for structured output tests
class SampleExtraction(BaseModel):
    title: str
    key_finding: str
    confidence: float = Field(ge=0.0, le=1.0)


@pytest.fixture
def sample_router() -> RoleRouter:
    router = RoleRouter()
    # Configure ANALYST with OpenAI
    router.register(
        LLMRole.ANALYST,
        [
            ModelConfig(provider="fake", model="gpt-4o", family="openai"),
            ModelConfig(provider="fake", model="gpt-4o-mini", family="openai"),
        ],
    )
    # Configure WRITER with OpenAI
    router.register(
        LLMRole.WRITER,
        [ModelConfig(provider="fake", model="gpt-4o", family="openai")],
    )
    # Configure VERIFIER with Anthropic (different family!)
    router.register(
        LLMRole.VERIFIER,
        [ModelConfig(provider="fake", model="claude-3-5-sonnet", family="anthropic")],
    )
    # Configure READER with OpenAI
    router.register(
        LLMRole.READER,
        [ModelConfig(provider="fake", model="gpt-4o-mini", family="openai")],
    )
    return router


def test_role_router_family_separation(sample_router: RoleRouter) -> None:
    """Verifier MUST use a different model family than analyst/writer (ARCH §2)."""
    # Valid setup (Anthropic vs OpenAI) -> passes
    sample_router.validate_family_separation()

    # Invalid setup: change verifier family to 'openai' -> raises ValueError
    invalid_router = RoleRouter()
    invalid_router.register(
        LLMRole.ANALYST,
        [ModelConfig(provider="fake", model="gpt-4o", family="openai")],
    )
    invalid_router.register(
        LLMRole.VERIFIER,
        [ModelConfig(provider="fake", model="gpt-4o-mini", family="openai")],
    )

    with pytest.raises(ValueError, match="VERIFIER model family.*overlaps with ANALYST"):
        invalid_router.validate_family_separation()


def test_reader_tool_binding_prohibition(sample_router: RoleRouter) -> None:
    """READER role LLM calls MUST have NO tools bound (ARCHITECTURE §8 / Rule 5)."""
    provider = FakeProvider()
    gateway = LLMGateway(router=sample_router)
    gateway.register_provider("fake", provider)

    # Calling READER without tools -> OK
    provider.add_canned_response('{"status": "ok"}')
    res = gateway.complete(role=LLMRole.READER, prompt="Analyze paper text")
    assert res.raw_content == '{"status": "ok"}'

    # Calling READER with tools -> Raises ReaderToolBindingError
    dummy_tool = {"name": "search", "description": "search tool"}
    with pytest.raises(ReaderToolBindingError, match="Guard violation: READER_NO_TOOLS"):
        gateway.complete(role=LLMRole.READER, prompt="Analyze paper text", tools=[dummy_tool])


def test_budget_cap_enforcement(sample_router: RoleRouter) -> None:
    """Gateway enforces token/usd limits via omni_core.budget.BudgetTracker."""
    tracker = BudgetTracker()
    tracker.set_limit("prompt_tokens", 150.0)

    provider = FakeProvider()
    provider.add_canned_response("Response 1", prompt_tokens=100)
    provider.add_canned_response("Response 2", prompt_tokens=100)

    gateway = LLMGateway(router=sample_router, budget_tracker=tracker)
    gateway.register_provider("fake", provider)

    # First call uses 100 prompt tokens (limit 150) -> succeeds
    gateway.complete(role=LLMRole.ANALYST, prompt="Prompt 1")
    assert tracker.usage("prompt_tokens") == 100.0

    # Second call uses 100 prompt tokens (total 200 >= 150) -> raises BudgetExceeded
    with pytest.raises(BudgetExceeded, match="Budget exceeded for prompt_tokens"):
        gateway.complete(role=LLMRole.ANALYST, prompt="Prompt 2")


def test_redaction(sample_router: RoleRouter) -> None:
    """Secrets in prompts are redacted before sending to LLM (Non-negotiable Rule 9)."""
    provider = FakeProvider()
    provider.add_canned_response("Done")

    gateway = LLMGateway(router=sample_router)
    gateway.register_provider("fake", provider)

    prompt_with_secret = "Here is my key: sk-abcdef12345678901234567890 and Bearer xyz.123.abc"
    gateway.complete(role=LLMRole.ANALYST, prompt=prompt_with_secret)

    recorded = provider.recorded_calls[0]
    assert "sk-abcdef12345678901234567890" not in recorded.prompt
    assert "Bearer xyz.123.abc" not in recorded.prompt
    assert "[REDACTED_SECRET]" in recorded.prompt


def test_circuit_breaker() -> None:
    """Circuit breaker trips to OPEN on repeated failures and blocks execution."""
    cb = CircuitBreaker("fake:gpt-4o", failure_threshold=2, recovery_timeout=60.0)
    assert cb.state == CircuitState.CLOSED

    # First failure
    cb.record_failure(RuntimeError("500 internal error"))
    assert cb.state == CircuitState.CLOSED

    # Second failure -> trips to OPEN
    cb.record_failure(RuntimeError("500 internal error"))
    assert cb.state == CircuitState.OPEN

    # Executing check_allowed while OPEN raises CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError, match="Circuit breaker is OPEN for fake:gpt-4o"):
        cb.check_allowed()


def test_primary_to_fallback_failover(sample_router: RoleRouter) -> None:
    """Gateway falls back to secondary ModelConfig when primary model fails."""
    provider = FakeProvider()

    # Configure custom handler: gpt-4o fails, gpt-4o-mini succeeds
    def handler(_prompt: str, config: ModelConfig) -> FakeLLMResponse:
        if config.model == "gpt-4o":
            return FakeLLMResponse(content="", should_raise=RuntimeError("Primary model OOM"))
        return FakeLLMResponse(content="Fallback response")

    provider.set_custom_handler(handler)

    gateway = LLMGateway(
        router=sample_router,
        circuit_breaker_failure_threshold=1,  # Trip CB on 1st error
    )
    gateway.register_provider("fake", provider)

    # Call ANALYST role (primary: gpt-4o, fallback: gpt-4o-mini)
    res = gateway.complete(role=LLMRole.ANALYST, prompt="Run analysis")

    assert res.raw_content == "Fallback response"
    assert res.model_config.model == "gpt-4o-mini"


def test_structured_output_repair(sample_router: RoleRouter) -> None:
    """Gateway retries up to 2 times on schema validation errors with repair prompts."""
    provider = FakeProvider()
    # 1st response: invalid JSON
    provider.add_canned_response("Not a json object")
    # 2nd response: valid JSON for SampleExtraction
    provider.add_canned_response(
        '{"title": "Test Paper", "key_finding": "High accuracy", "confidence": 0.95}'
    )

    gateway = LLMGateway(router=sample_router)
    gateway.register_provider("fake", provider)

    res = gateway.complete_structured(
        role=LLMRole.ANALYST,
        prompt="Extract findings",
        schema=SampleExtraction,
    )

    assert res.parsed is not None
    assert res.parsed.title == "Test Paper"
    assert res.parsed.confidence == 0.95
    assert res.repair_attempts == 1


def test_structured_output_repair_exhaustion(sample_router: RoleRouter) -> None:
    """Gateway raises SchemaRepairError after 2 failed repair attempts (3 attempts total)."""
    provider = FakeProvider()
    # 3 consecutive invalid responses
    provider.add_canned_response('{"title": "Missing required fields"}')
    provider.add_canned_response('{"title": "Still missing fields"}')
    provider.add_canned_response('{"title": "Also missing fields"}')

    gateway = LLMGateway(router=sample_router)
    gateway.register_provider("fake", provider)

    with pytest.raises(SchemaRepairError, match="Failed to generate valid structured output after 2 repair attempts"):
        gateway.complete_structured(
            role=LLMRole.ANALYST,
            prompt="Extract findings",
            schema=SampleExtraction,
        )


def test_fake_provider_cassette(sample_router: RoleRouter) -> None:
    """FakeProvider supports saving and replaying cassettes."""
    provider = FakeProvider()
    provider.add_canned_response("Cassette content 1")

    gateway = LLMGateway(router=sample_router)
    gateway.register_provider("fake", provider)

    gateway.complete(role=LLMRole.ANALYST, prompt="Test cassette prompt")

    with tempfile.TemporaryDirectory() as tmpdir:
        cassette_path = Path(tmpdir) / "test_cassette.json"
        provider.save_cassette(cassette_path)
        assert cassette_path.exists()

        # Replay cassette with a fresh provider
        replay_provider = FakeProvider()
        replay_provider.load_cassette(cassette_path)

        replay_gateway = LLMGateway(router=sample_router)
        replay_gateway.register_provider("fake", replay_provider)

        res = replay_gateway.complete(role=LLMRole.ANALYST, prompt="Replayed call")
        assert res.raw_content == "Cassette content 1"
