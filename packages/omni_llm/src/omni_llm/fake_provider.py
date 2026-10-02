"""FakeProvider and cassette replay system for deterministic offline testing (Non-negotiable Rule 9)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from omni_llm.roles import ModelConfig


@dataclass
class FakeLLMResponse:
    """Simulated response from FakeProvider."""

    content: str
    prompt_tokens: int = 100
    completion_tokens: int = 50
    cost_usd: float = 0.001
    should_raise: Exception | None = None


@dataclass
class RecordedCall:
    """Record of an LLM call made to FakeProvider."""

    prompt: str
    system_prompt: str | None
    model_config: ModelConfig
    tools_bound: bool
    response_content: str


class FakeProvider:
    """Fake LLM provider for unit/integration testing without network/API keys."""

    def __init__(self) -> None:
        self.default_response = FakeLLMResponse(content='{"status": "ok"}')
        self._canned_responses: list[FakeLLMResponse] = []
        self._prompt_mapping: dict[str, FakeLLMResponse] = {}
        self._custom_handler: Callable[[str, ModelConfig], FakeLLMResponse] | None = None
        self.recorded_calls: list[RecordedCall] = []
        self.cassette_path: Path | None = None

    def add_canned_response(
        self,
        content: str,
        prompt_tokens: int = 100,
        completion_tokens: int = 50,
        cost_usd: float = 0.001,
        should_raise: Exception | None = None,
    ) -> None:
        """Enqueue a canned response to be returned sequentially."""
        self._canned_responses.append(
            FakeLLMResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost_usd=cost_usd,
                should_raise=should_raise,
            )
        )

    def add_prompt_response(self, prompt_substring: str, response: FakeLLMResponse) -> None:
        """Map a prompt substring to a specific response."""
        self._prompt_mapping[prompt_substring] = response

    def set_custom_handler(
        self, handler: Callable[[str, ModelConfig], FakeLLMResponse]
    ) -> None:
        """Set a dynamic callback handler for generating responses."""
        self._custom_handler = handler

    def load_cassette(self, path: Path | str) -> None:
        """Load a cassette JSON file containing recorded responses."""
        self.cassette_path = Path(path)
        if self.cassette_path.exists():
            data = json.loads(self.cassette_path.read_text(encoding="utf-8"))
            for item in data.get("responses", []):
                self.add_canned_response(
                    content=item["content"],
                    prompt_tokens=item.get("prompt_tokens", 100),
                    completion_tokens=item.get("completion_tokens", 50),
                    cost_usd=item.get("cost_usd", 0.001),
                )

    def save_cassette(self, path: Path | str) -> None:
        """Save recorded calls to a cassette file."""
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "responses": [
                {
                    "prompt": c.prompt,
                    "content": c.response_content,
                    "model": c.model_config.model,
                }
                for c in self.recorded_calls
            ]
        }
        target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def invoke(
        self,
        prompt: str,
        model_config: ModelConfig,
        system_prompt: str | None = None,
        tools_bound: bool = False,
    ) -> FakeLLMResponse:
        """Execute a simulated LLM call."""
        # 1. Custom handler
        if self._custom_handler is not None:
            resp = self._custom_handler(prompt, model_config)
        # 2. Prompt mapping
        elif any(key in prompt for key in self._prompt_mapping):
            matching_key = next(key for key in self._prompt_mapping if key in prompt)
            resp = self._prompt_mapping[matching_key]
        # 3. Canned queue
        elif self._canned_responses:
            resp = self._canned_responses.pop(0)
        # 4. Fallback default
        else:
            resp = self.default_response

        # Record call history
        self.recorded_calls.append(
            RecordedCall(
                prompt=prompt,
                system_prompt=system_prompt,
                model_config=model_config,
                tools_bound=tools_bound,
                response_content=resp.content if not resp.should_raise else "<ERROR>",
            )
        )

        if resp.should_raise:
            raise resp.should_raise

        return resp

    def clear(self) -> None:
        """Reset all canned responses and call history."""
        self._canned_responses.clear()
        self._prompt_mapping.clear()
        self.recorded_calls.clear()
        self._custom_handler = None
