"""LLM Gateway package for OmniResearch."""

from omni_llm.circuit_breaker import CircuitBreaker, CircuitState
from omni_llm.exceptions import (
    CircuitBreakerOpenError,
    LLMError,
    ProviderError,
    ReaderToolBindingError,
    SchemaRepairError,
)
from omni_llm.fake_provider import FakeLLMResponse, FakeProvider, RecordedCall
from omni_llm.gateway import LLMGateway, LLMResult
from omni_llm.redactor import Redactor
from omni_llm.roles import LLMRole, ModelConfig, RoleRouter

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    "FakeLLMResponse",
    "FakeProvider",
    "LLMError",
    "LLMGateway",
    "LLMResult",
    "LLMRole",
    "ModelConfig",
    "ProviderError",
    "ReaderToolBindingError",
    "RecordedCall",
    "Redactor",
    "RoleRouter",
    "SchemaRepairError",
]
