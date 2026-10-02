"""LLM role definitions and model family routing.

Each agent is assigned a role that determines which provider/model family it uses.
The verifier role MUST use a different model family than analyst/writer to ensure
independent verification (ARCHITECTURE §2).
"""

from __future__ import annotations

from enum import StrEnum, unique
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


@unique
class LLMRole(StrEnum):
    """Roles that determine model selection and tool binding.

    - READER: processes untrusted content, NO tools bound (ARCHITECTURE §8)
    - PLANNER: research planning, cheap models, no code execution
    - ANALYST: analysis and interpretation
    - WRITER: report generation
    - VERIFIER: independent verification — MUST use different model family than analyst/writer
    - CODER: code generation for experiments
    """

    READER = "READER"
    PLANNER = "PLANNER"
    ANALYST = "ANALYST"
    WRITER = "WRITER"
    VERIFIER = "VERIFIER"
    CODER = "CODER"


class ModelConfig(BaseModel):
    """Configuration for a model within a provider."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    family: str  # e.g. "openai", "anthropic", "google" — for family separation enforcement
    max_tokens: int = Field(default=4096, gt=0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    extra_params: dict[str, Any] = Field(default_factory=dict)


class RoleRouter:
    """Routes LLM requests to the correct model based on the agent's role.

    Enforces that verifier family != analyst/writer family.
    """

    def __init__(self) -> None:
        self._role_configs: dict[LLMRole, list[ModelConfig]] = {}
        self._default_config: ModelConfig | None = None

    def register(self, role: LLMRole, configs: list[ModelConfig]) -> None:
        """Register model configurations for a role (primary + fallbacks)."""
        if not configs:
            msg = f"Must provide at least one ModelConfig for role {role}"
            raise ValueError(msg)
        self._role_configs[role] = configs

    def set_default(self, config: ModelConfig) -> None:
        """Set a default model for roles without explicit configuration."""
        self._default_config = config

    def get_configs(self, role: LLMRole) -> list[ModelConfig]:
        """Get model configs for a role (primary + fallbacks)."""
        configs = self._role_configs.get(role)
        if configs:
            return configs
        if self._default_config:
            return [self._default_config]
        msg = f"No model configured for role {role} and no default set"
        raise ValueError(msg)

    def get_primary(self, role: LLMRole) -> ModelConfig:
        """Get the primary model config for a role."""
        return self.get_configs(role)[0]

    def validate_family_separation(self) -> None:
        """Verify that VERIFIER uses a different model family than ANALYST and WRITER.

        Raises ValueError if the constraint is violated.
        """
        verifier_configs = self._role_configs.get(LLMRole.VERIFIER)
        if not verifier_configs:
            return  # No verifier configured yet; nothing to validate

        verifier_families = {c.family for c in verifier_configs}

        for role in (LLMRole.ANALYST, LLMRole.WRITER):
            role_configs = self._role_configs.get(role)
            if not role_configs:
                continue
            role_families = {c.family for c in role_configs}
            overlap = verifier_families & role_families
            if overlap:
                msg = (
                    f"VERIFIER model family {overlap} overlaps with {role.value} "
                    f"family. Verifier must use a different model family "
                    f"for independent verification."
                )
                raise ValueError(msg)
