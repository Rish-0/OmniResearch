"""LLM Gateway: role routing, circuit breaker, fallbacks, structured output repair, budget tracking, and safety guards."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from omni_core.budget import BudgetTracker
from omni_core.logging import get_logger
from omni_llm.circuit_breaker import CircuitBreaker
from omni_llm.exceptions import (
    CircuitBreakerOpenError,
    ProviderError,
    ReaderToolBindingError,
    SchemaRepairError,
)
from omni_llm.fake_provider import FakeProvider
from omni_llm.redactor import Redactor
from omni_llm.roles import LLMRole, ModelConfig, RoleRouter

logger = get_logger("omni_llm.gateway")

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResult[T]:
    """Result container for an LLM gateway invocation."""

    raw_content: str
    parsed: T | None
    model_config: ModelConfig
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    repair_attempts: int = 0


class LLMGateway:
    """Central gateway for all LLM interactions in OmniResearch.

    Handles:
    - Role-based routing (ARCH §2)
    - READER tool binding prohibition (ARCH §8 / Rule 5)
    - Budget cap enforcement (omni_core.budget.BudgetTracker)
    - Secret redaction (omni_llm.redactor.Redactor)
    - Circuit breaker per provider/model (omni_llm.circuit_breaker.CircuitBreaker)
    - Primary -> Fallback failover
    - Structured output validation with <= 2 repair retries
    """

    def __init__(
        self,
        router: RoleRouter,
        budget_tracker: BudgetTracker | None = None,
        redactor: Redactor | None = None,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_recovery_timeout: float = 30.0,
    ) -> None:
        self.router = router
        self.budget_tracker = budget_tracker or BudgetTracker()
        self.redactor = redactor or Redactor()
        self.circuit_breaker_threshold = circuit_breaker_failure_threshold
        self.circuit_breaker_timeout = circuit_breaker_recovery_timeout

        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._providers: dict[str, Any] = {}

    def register_provider(self, provider_name: str, provider_instance: Any) -> None:
        """Register a provider implementation (e.g. FakeProvider or real provider client)."""
        self._providers[provider_name] = provider_instance

    def _get_circuit_breaker(self, config: ModelConfig) -> CircuitBreaker:
        """Get or create circuit breaker for provider:model endpoint."""
        key = f"{config.provider}:{config.model}"
        if key not in self._circuit_breakers:
            self._circuit_breakers[key] = CircuitBreaker(
                name=key,
                failure_threshold=self.circuit_breaker_threshold,
                recovery_timeout=self.circuit_breaker_timeout,
            )
        return self._circuit_breakers[key]

    def complete(
        self,
        role: LLMRole,
        prompt: str,
        system_prompt: str | None = None,
        tools: list[Any] | None = None,
    ) -> LLMResult[Any]:
        """Execute a text LLM call with role routing, fallbacks, and budget checks."""
        return self._execute_call(
            role=role,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            schema=None,
        )

    def complete_structured(
        self,
        role: LLMRole,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        tools: list[Any] | None = None,
    ) -> LLMResult[T]:
        """Execute a structured output LLM call with <= 2 repair retries on validation failure."""
        return self._execute_call(
            role=role,
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            schema=schema,
        )

    def _execute_call(
        self,
        role: LLMRole,
        prompt: str,
        system_prompt: str | None,
        tools: list[Any] | None,
        schema: type[T] | None,
    ) -> LLMResult[T]:
        # Guard check: READER role cannot have tools bound (ARCHITECTURE §8 / Rule 5)
        if role == LLMRole.READER and tools is not None and len(tools) > 0:
            raise ReaderToolBindingError("READER role calls MUST have NO tools bound.")

        # Enforce verifier separation if configured
        self.router.validate_family_separation()

        # Redact secrets from input prompt
        redacted_prompt = self.redactor.redact_text(prompt)
        redacted_system = self.redactor.redact_text(system_prompt) if system_prompt else None

        # Check budget before proceeding
        self.budget_tracker.record("llm_calls", 1.0)

        # Get list of model configs for role (primary + fallbacks)
        configs = self.router.get_configs(role)
        last_error: Exception | None = None

        for config in configs:
            cb = self._get_circuit_breaker(config)
            try:
                cb.check_allowed()
            except CircuitBreakerOpenError as exc:
                logger.warning(
                    f"Skipping {config.provider}:{config.model} - circuit breaker OPEN"
                )
                last_error = exc
                continue

            try:
                result = self._dispatch_with_schema_repair(
                    config=config,
                    prompt=redacted_prompt,
                    system_prompt=redacted_system,
                    tools_bound=bool(tools),
                    schema=schema,
                )
                cb.record_success()
                # Record budget usage
                self.budget_tracker.record("prompt_tokens", result.prompt_tokens)
                self.budget_tracker.record("completion_tokens", result.completion_tokens)
                self.budget_tracker.record("llm_usd", result.cost_usd)
                return result
            except Exception as exc:
                cb.record_failure(exc)
                logger.error(
                    f"Call to {config.provider}:{config.model} failed: {exc}"
                )
                last_error = exc

        if last_error:
            raise last_error
        raise ProviderError("No available model configuration succeeded.")

    def _dispatch_with_schema_repair(
        self,
        config: ModelConfig,
        prompt: str,
        system_prompt: str | None,
        tools_bound: bool,
        schema: type[T] | None,
    ) -> LLMResult[T]:
        provider = self._providers.get(config.provider)
        if not provider:
            raise ProviderError(f"Provider {config.provider} not registered in LLMGateway")

        current_prompt = prompt
        if schema:
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            current_prompt += f"\n\nRespond strictly with JSON matching this schema:\n{schema_json}"

        max_repair_attempts = 2
        attempt = 0

        while attempt <= max_repair_attempts:
            if isinstance(provider, FakeProvider):
                resp = provider.invoke(
                    prompt=current_prompt,
                    model_config=config,
                    system_prompt=system_prompt,
                    tools_bound=tools_bound,
                )
                raw_content = resp.content
                prompt_tokens = resp.prompt_tokens
                completion_tokens = resp.completion_tokens
                cost_usd = resp.cost_usd
            else:
                msg = f"Unsupported provider interface: {type(provider)}"
                raise ProviderError(msg)

            if schema is None:
                return LLMResult(
                    raw_content=raw_content,
                    parsed=None,
                    model_config=config,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost_usd,
                    repair_attempts=0,
                )

            # Try parsing structured output
            parsed, parse_error = self._parse_json_schema(raw_content, schema)
            if parsed is not None:
                return LLMResult(
                    raw_content=raw_content,
                    parsed=parsed,
                    model_config=config,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost_usd,
                    repair_attempts=attempt,
                )

            # Validation failed, prepare repair retry prompt
            attempt += 1
            if attempt <= max_repair_attempts:
                logger.warning(
                    f"Structured output schema validation failed (attempt {attempt}/{max_repair_attempts}). Retrying..."
                )
                current_prompt += (
                    f"\n\n[REPAIR RETRY {attempt}]\nYour previous response failed validation with error:\n"
                    f"{parse_error}\n"
                    f"Please fix the error and output valid JSON matching the schema."
                )

        raise SchemaRepairError(
            attempts=max_repair_attempts,
            last_error=parse_error or "Unknown validation error",
        )

    def _parse_json_schema(
        self, raw_content: str, schema: type[T]
    ) -> tuple[T | None, str | None]:
        clean_content = raw_content.strip()
        # Extract markdown json block if wrapped
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_content)
        if match:
            clean_content = match.group(1).strip()

        try:
            parsed = schema.model_validate_json(clean_content)
            return parsed, None
        except (ValidationError, json.JSONDecodeError) as exc:
            return None, str(exc)
